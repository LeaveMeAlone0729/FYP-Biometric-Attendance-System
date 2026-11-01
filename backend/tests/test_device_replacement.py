"""C1 actual REST/crypto/transaction tests; all keys and records are disposable."""
import base64,json,os,re,secrets,unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from sqlalchemy import select,func
import test_device_activation as activation
from modules.devices.models import RegisteredDevice
from modules.devices.pending_models import PendingDeviceRegistration
from modules.devices.biometric_models import DeviceBiometricSession
from modules.devices.crypto import canonical_public_key
from modules.devices.approval_provider import ApprovalBinding
from modules.devices.service import DeviceRegistrationError
from models import Attendance
from config import Settings
from database import make_engine
from security import hash_password

class ReplacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.password_hash=hash_password('test-password')
    def setUp(self):
        self.h=activation.ActivationTests();self.h.password_hash=self.password_hash
        if hasattr(self,'engine_override'):self.h.engine_override=self.engine_override
        self.h.setUp();self.f=self.h.f
        result=self.f.client.post('/api/v1/devices/pending-registrations/'+self.h.identifier+'/cancel',headers=self.f.headers,json={})
        self.assertEqual(result.status_code,200,result.text)
        self.second_key=ec.generate_private_key(ec.SECP256R1())
        public=base64.b64encode(self.second_key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
        public,fingerprint=canonical_public_key(public)
        with self.f.sessions.begin() as db:
            db.add(RegisteredDevice(device_id='isolated-slot-two',student_id='DEVICE001',slot_number=2,public_key_spki=public,
                public_key_fingerprint=fingerprint,device_name='fixture tablet',device_model='fixture',platform='android',status='ACTIVE',registered_at=self.f.fixture.now))
        self.before=self.rows()
    def tearDown(self):self.h.tearDown()
    def rows(self):
        with self.f.sessions() as db:
            return {d.device_id:{c.name:getattr(d,c.name) for c in RegisteredDevice.__table__.columns} for d in db.scalars(select(RegisteredDevice))}
    def begin(self,slot=1,**changes):
        body={**self.h.p.body,'slot_number':slot,'old_device_id':self.f.device_id if slot==1 else 'isolated-slot-two',**changes}
        return self.f.client.post('/api/v1/devices/replacements',headers=self.f.headers,json=body)
    def prepare(self,slot=1):
        result=self.begin(slot);self.assertEqual(result.status_code,201,result.text)
        pending=result.json();self.h.identifier=pending['pending_registration_id']
        self.assertEqual(self.h.p.prove(pending).status_code,200)
        with self.f.sessions.begin() as db:
            row=db.get(PendingDeviceRegistration,self.h.identifier)
            binding=ApprovalBinding('DEVICE001',row.auth_token_hash,row.pending_registration_id,row.candidate_device_id,row.public_key_fingerprint,row.slot_number,row.operation,row.slot_one_device_id,row.replaced_device_fingerprint)
            db.get(activation.FixtureGrant,'grant-1').binding=json.dumps(binding.__dict__)
            db.get(activation.FixtureResult,'trusted-result-1').binding=json.dumps(binding.__dict__)
        self.h.binding=binding
        return pending
    def post(self,suffix,data,headers=None):
        return self.f.client.post('/api/v1/devices/pending-registrations/'+self.h.identifier+suffix,headers=headers or self.f.headers,json=data)
    def challenge(self):
        response=self.post('/activation-challenges',{'approval_id':'grant-1'})
        self.assertEqual(response.status_code,201,response.text);return response.json()
    def activate(self,challenge,key=None,headers=None):
        return self.post('/activate',{'approval_id':'grant-1','challenge_id':challenge['challenge_id'],'signature':self.h.signature(challenge,key)},headers)
    def assert_unchanged(self):
        self.assertEqual(self.rows(),self.before)
        self.assertEqual(self.h.count(Attendance),0)
    def successful(self,slot):
        pending=self.prepare(slot)
        target=self.h.binding.replaced_device_id
        # A previously issued Phase 2 proof must also fail after revocation.
        verification=self.f.issue(fingerprint=self.before[target]['public_key_fingerprint']).json()
        with patch('modules.devices.activation_service.trusted_approval_provider',return_value=self.h.provider):
            ready=self.post('/activation-readiness',{});self.assertEqual(ready.status_code,200,ready.text)
            challenge=self.challenge();payload=json.loads(base64.b64decode(challenge['signing_payload']))
            self.assertEqual(payload['replaced_device_id'],target)
            result=self.activate(challenge);self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(self.activate(challenge).json()['code'],'ACTIVATION_REPLAYED')
        after=self.rows();self.assertEqual(after[target]['status'],'REVOKED')
        self.assertEqual(after[pending['candidate_device_id']]['status'],'ACTIVE')
        self.assertEqual(after[pending['candidate_device_id']]['slot_number'],slot)
        for identifier,row in self.before.items():
            if identifier!=target:self.assertEqual(after[identifier],row)
        listing=self.f.client.get('/api/v1/devices',headers=self.f.headers).json()
        self.assertEqual(listing['active_count'],2)
        status=self.f.client.get('/api/v1/devices/pending-registrations/'+self.h.identifier+'/activation-status',headers=self.f.headers).json()
        self.assertEqual(status['status'],'ACTIVE')
        self.assertNotEqual(self.f.issue(fingerprint=self.before[target]['public_key_fingerprint']).status_code,201)
        self.assertNotEqual(self.f.confirm(verification,key=self.f.key if slot==1 else self.second_key).status_code,200)
        self.assertEqual(self.h.count(Attendance),0)
    def test_slot_one_replacement_and_revoked_proof_rejection(self):self.successful(1)
    def test_slot_two_replacement_preserves_slot_one(self):self.successful(2)
    def test_wrong_student_slot_and_existing_key_rejected(self):
        self.assertEqual(self.begin(2,old_device_id=self.f.device_id).status_code,404)
        other=self.f.fixture.login('DEVICE002')
        result=self.f.client.post('/api/v1/devices/replacements',headers=other,json={**self.h.p.body,'slot_number':1,'old_device_id':self.f.device_id})
        self.assertEqual(result.status_code,404)
        self.assertEqual(self.begin(public_key_spki=self.before[self.f.device_id]['public_key_spki']).json()['code'],'KEY_ALREADY_REGISTERED')
        self.assert_unchanged()
    def test_duplicate_conflict_cancel_and_restart(self):
        first=self.begin().json();self.assertEqual(self.begin().json()['pending_registration_id'],first['pending_registration_id'])
        self.assertEqual(self.begin(2).json()['code'],'PENDING_EXISTS')
        status=self.f.client.get('/api/v1/devices/pending-registrations/current',headers=self.f.headers).json()['pending']
        self.assertEqual(status['replaced_device_id'],self.f.device_id)
        cancelled=self.f.client.post('/api/v1/devices/pending-registrations/'+first['pending_registration_id']+'/cancel',headers=self.f.headers,json={})
        self.assertEqual(cancelled.json()['status'],'CANCELLED')
        self.assertEqual(self.h.p.prove(first).status_code,409)
        self.assertNotEqual(self.begin().json()['pending_registration_id'],first['pending_registration_id']);self.assert_unchanged()
    def test_invalid_proof_and_expiry(self):
        first=self.begin().json();self.assertEqual(self.h.p.prove(first,self.f.key).json()['code'],'INVALID_SIGNATURE')
        second=self.begin().json();self.f.fixture.now+=timedelta(seconds=121)
        self.assertEqual(self.h.p.prove(second).status_code,410);self.assert_unchanged()
    def test_unavailable_untrusted_and_wrong_binding_fail_closed(self):
        self.prepare()
        self.assertEqual(self.post('/activation-readiness',{}).json()['code'],'APPROVAL_UNAVAILABLE')
        with patch('modules.devices.activation_service.trusted_approval_provider',return_value=self.h.provider):
            for changes in [{'operation':'enroll_second_device'},{'slot_number':2},{'replaced_device_id':'wrong'},{'replaced_device_fingerprint':'wrong'},{'student_id':'DEVICE002'},{'auth_token_hash':'wrong'}]:
                with self.f.sessions.begin() as db:db.get(activation.FixtureGrant,'grant-1').binding=json.dumps({**self.h.binding.__dict__,**changes})
                self.assertEqual(self.post('/activation-challenges',{'approval_id':'grant-1'}).json()['code'],'APPROVAL_MISMATCH')
            with self.f.sessions.begin() as db:
                grant=db.get(activation.FixtureGrant,'grant-1');grant.binding=json.dumps(self.h.binding.__dict__);grant.result='COMPLETED_UNTRUSTED'
            self.assertEqual(self.post('/activation-challenges',{'approval_id':'grant-1'}).json()['code'],'BIOMETRIC_TRUST_REQUIRED')
        self.assert_unchanged()
    def test_session_signature_expiry_replay_and_changed_target(self):
        self.prepare()
        with patch('modules.devices.activation_service.trusted_approval_provider',return_value=self.h.provider):
            challenge=self.challenge()
            self.assertEqual(self.activate(challenge,headers=self.f.fixture.login('DEVICE001')).status_code,404)
            self.assertEqual(self.activate(challenge,key=self.f.key).json()['code'],'INVALID_ACTIVATION_SIGNATURE')
            self.assertEqual(self.activate(challenge).json()['code'],'ACTIVATION_REPLAYED')
            challenge=self.challenge();self.f.fixture.now+=timedelta(seconds=61)
            self.assertEqual(self.activate(challenge).status_code,410)
        self.assert_unchanged()
    def test_expired_consumed_or_invalid_revision_approval_preserves_old_device(self):
        self.prepare()
        with patch('modules.devices.activation_service.trusted_approval_provider',return_value=self.h.provider):
            for field,value,code in [('expires_at',self.f.fixture.now,'APPROVAL_EXPIRED'),('consumed_at',self.f.fixture.now,'APPROVAL_USED')]:
                with self.f.sessions.begin() as db:
                    grant=db.get(activation.FixtureGrant,'grant-1');grant.expires_at=self.f.fixture.now+timedelta(seconds=60);grant.consumed_at=None
                    setattr(grant,field,value)
                self.assertEqual(self.post('/activation-challenges',{'approval_id':'grant-1'}).json()['code'],code)
            with self.f.sessions.begin() as db:
                grant=db.get(activation.FixtureGrant,'grant-1');grant.expires_at=self.f.fixture.now+timedelta(seconds=60);grant.consumed_at=None
                db.get(activation.FixtureRevision,'revision-1').trusted=False
            self.assertEqual(self.post('/activation-challenges',{'approval_id':'grant-1'}).json()['code'],'BIOMETRIC_TRUST_REQUIRED')
        self.assert_unchanged()

    def test_failed_face_ends_pending_replacement_without_revocation(self):
        pending=self.prepare()
        response=self.f.client.post('/api/v1/device-approvals',headers=self.f.headers,json={'pending_registration_id':pending['pending_registration_id']})
        identifier=response.json()['approval_id']
        rejected=self.f.client.post('/api/v1/device-approvals/'+identifier+'/face',headers=self.f.headers,files={'file':('frame.jpg',b'other-face','image/jpeg')})
        self.assertEqual(rejected.json()['code'],'FACE_NOT_MATCHED')
        with self.f.sessions() as db:self.assertEqual(db.get(PendingDeviceRegistration,self.h.identifier).status,'FAILED')
        self.assert_unchanged()

    def test_cancelled_inflight_activation_cannot_revoke_target(self):
        self.prepare()
        with patch('modules.devices.activation_service.trusted_approval_provider',return_value=self.h.provider):
            challenge=self.challenge();self.post('/cancel',{})
            self.assertEqual(self.activate(challenge).json()['code'],'CANDIDATE_PROOF_REQUIRED')
        self.assert_unchanged()

    def test_mutated_slot_or_old_fingerprint_rejected(self):
        self.prepare()
        with self.f.sessions.begin() as db:db.get(PendingDeviceRegistration,self.h.identifier).slot_number=2
        self.assertEqual(self.post('/activation-readiness',{}).json()['code'],'REPLACEMENT_BINDING_MISMATCH');self.assert_unchanged()
    def test_insert_failure_rolls_back_revocation_and_grant(self):
        pending=self.prepare()
        with patch('modules.devices.activation_service.trusted_approval_provider',return_value=self.h.provider):
            challenge=self.challenge()
            with self.f.sessions.begin() as db:
                # Deliberate isolated PK conflict AFTER approval validation to exercise savepoint rollback.
                row=db.get(RegisteredDevice,'isolated-slot-two')
                row.device_id=pending['candidate_device_id']
            self.before=self.rows()
            response=self.activate(challenge);self.assertEqual(response.json()['code'],'ACTIVATION_CONFLICT')
        self.assert_unchanged()
        with self.f.sessions() as db:self.assertIsNone(db.get(activation.FixtureGrant,'grant-1').consumed_at)
    def test_replacement_biometrics_reuse_untrusted_workflow(self):
        pending=self.prepare(2)
        response=self.f.client.post('/api/v1/device-approvals',headers=self.f.headers,json={'pending_registration_id':pending['pending_registration_id']})
        self.assertEqual(response.status_code,201,response.text)
        result=response.json();self.assertEqual(result['operation'],'replace_device');self.assertEqual(result['slot_number'],2)
        self.assertFalse(result['trusted']);self.assert_unchanged()

@unittest.skipUnless(os.getenv('ATTENDANCE_DEVICE_MYSQL_TESTS')=='1','Opt-in isolated MariaDB replacement race')
class ReplacementMariaDBTests(unittest.TestCase):
    def test_serialized_replacements_and_activation_replay(self):
        import mysql.connector
        settings=Settings();schema='attendance_c1_test_'+secrets.token_hex(6)
        connection=mysql.connector.connect(host=settings.db_host,port=settings.db_port,user=settings.db_user,password=settings.db_password)
        harness=ReplacementTests();created=False
        try:
            with connection.cursor() as c:c.execute('CREATE DATABASE `'+schema+'` CHARACTER SET utf8mb4')
            created=True;harness.engine_override=make_engine(replace(settings,db_name=schema));harness.password_hash=hash_password('test-password');harness.setUp()
            # Both slots occupied: requests reserve no third slot and serialize on the student row.
            with ThreadPoolExecutor(max_workers=2) as pool:responses=list(pool.map(lambda slot:harness.begin(slot),[1,2]))
            self.assertEqual(sorted(r.status_code for r in responses),[201,409])
            pending=next(r.json() for r in responses if r.status_code==201)
            harness.f.client.post('/api/v1/devices/pending-registrations/'+pending['pending_registration_id']+'/cancel',headers=harness.f.headers,json={})
            harness.prepare(1)
            with patch('modules.devices.activation_service.trusted_approval_provider',return_value=harness.h.provider):
                challenge=harness.challenge()
                with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:harness.activate(challenge),range(2)))
            self.assertEqual(sorted(r.status_code for r in results),[200,409])
            self.assertEqual(next(r for r in results if r.status_code==409).json()['code'],'ACTIVATION_REPLAYED')
            self.assertEqual(harness.f.client.get('/api/v1/devices',headers=harness.f.headers).json()['active_count'],2)
            self.assertEqual(harness.h.count(Attendance),0)
            self.assertEqual(harness.rows()['isolated-slot-two'],harness.before['isolated-slot-two'])
        finally:
            if hasattr(harness,'h'):harness.tearDown()
            if created:
                assert re.fullmatch('attendance_c1_test_[0-9a-f]{12}',schema) and schema!=settings.db_name
                with connection.cursor() as c:c.execute('DROP DATABASE `'+schema+'`')
            connection.close()
