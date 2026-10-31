"""B4 private-core fixtures only. No trusted provider/mock exists in production."""
import base64
import hashlib
import json
import os
import re
import secrets
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import Boolean,DateTime,String,Text,select,func
from sqlalchemy.orm import Mapped,mapped_column
from config import Settings
from database import make_engine
from models import Base,Student,AuthSession,Attendance
from security import digest,encrypt_encoding,hash_password
from modules.devices.activation_models import DeviceActivationChallenge,DeviceActivationEvent
from modules.devices.activation_service import DeviceActivationService
from modules.devices.activation_migration import upgrade_activation_schema
from modules.devices.approval_provider import (ApprovalBinding,TrustedBiometricApproval,validate_approval,
    TrustedTemplateRevision,TrustedBiometricResult)
from modules.devices.pending_models import PendingDeviceRegistration
from modules.devices.models import RegisteredDevice
from modules.devices.crypto import canonical_public_key
from modules.devices.service import DeviceRegistrationError
import test_pending_device_enrollment as pending_tests


class FixtureRevision(Base):
    __tablename__='b4_fixture_revisions'
    revision_id: Mapped[str]=mapped_column(String(64),primary_key=True)
    student_id: Mapped[str]=mapped_column(String(64))
    template_hash: Mapped[str]=mapped_column(String(64))
    trusted: Mapped[bool]=mapped_column(Boolean)


class FixtureGrant(Base):
    __tablename__='b4_fixture_grants'
    approval_id: Mapped[str]=mapped_column(String(64),primary_key=True)
    binding: Mapped[str]=mapped_column(Text)
    revision_id: Mapped[str]=mapped_column(String(64))
    result: Mapped[str]=mapped_column(String(32))
    result_id: Mapped[str]=mapped_column(String(64),default='trusted-result-1')
    verified_at: Mapped[datetime]=mapped_column(DateTime)
    expires_at: Mapped[datetime]=mapped_column(DateTime)
    consumed_at: Mapped[datetime | None]=mapped_column(DateTime)


class FixtureResult(Base):
    __tablename__='activation_fixture_results'
    result_id: Mapped[str]=mapped_column(String(64),primary_key=True)
    binding: Mapped[str]=mapped_column(Text)
    revision_id: Mapped[str]=mapped_column(String(64))
    face_verified: Mapped[bool]=mapped_column(Boolean)
    liveness_verified: Mapped[bool]=mapped_column(Boolean)
    classification: Mapped[str]=mapped_column(String(40))
    verified_at: Mapped[datetime]=mapped_column(DateTime)
    expires_at: Mapped[datetime]=mapped_column(DateTime)


class FixtureProvider:
    """Persistent locked test grants/revisions; consume participates in caller transaction."""
    def validate_and_lock(self,db,identifier,binding,now):
        grant=db.scalar(select(FixtureGrant).where(FixtureGrant.approval_id==identifier).with_for_update())
        if grant is None:return None
        revision=db.scalar(select(FixtureRevision).where(FixtureRevision.revision_id==grant.revision_id).with_for_update())
        student=db.get(Student,binding.student_id)
        current_hash=hashlib.sha256((student.face_encoding or '').encode()).hexdigest()
        trusted=bool(revision and revision.trusted and revision.student_id==binding.student_id and revision.template_hash==current_hash)
        return TrustedBiometricApproval(grant.approval_id,ApprovalBinding(**json.loads(grant.binding)),
            grant.revision_id,trusted,grant.result,grant.verified_at,grant.expires_at,grant.consumed_at,grant.result_id)

    def current_template_revision(self,db,student_id,now):
        revision=db.scalar(select(FixtureRevision).where(FixtureRevision.student_id==student_id)
            .order_by(FixtureRevision.revision_id.desc()).with_for_update())
        return TrustedTemplateRevision(revision.revision_id,student_id,revision.template_hash,revision.trusted) if revision else None

    def validate_template_trust(self,db,revision,now):
        if not revision.trusted:raise DeviceRegistrationError(403,'BIOMETRIC_TRUST_REQUIRED','Untrusted fixture revision.')

    def invalidate_revision(self,db,student_id,revision_id,reason,now):
        row=db.get(FixtureRevision,revision_id);row.trusted=False

    def find_fresh_approval(self,db,binding,now):
        grant=db.scalar(select(FixtureGrant).where(FixtureGrant.binding==json.dumps(binding.__dict__),
            FixtureGrant.consumed_at==None,FixtureGrant.expires_at>now).with_for_update())
        return self.validate_and_lock(db,grant.approval_id,binding,now) if grant else None

    def validate_fresh_result(self,db,approval,binding,revision,now):
        row=db.scalar(select(FixtureResult).where(FixtureResult.result_id==approval.biometric_result_id).with_for_update())
        return TrustedBiometricResult(row.result_id,ApprovalBinding(**json.loads(row.binding)),row.revision_id,
            row.face_verified,row.liveness_verified,row.verified_at,row.expires_at,row.classification) if row else None

    def consume(self,db,approval,now):
        current=self.validate_and_lock(db,approval.approval_id,approval.binding,now)
        validate_approval(current,approval.approval_id,approval.binding,now)
        db.get(FixtureGrant,approval.approval_id).consumed_at=now
        db.flush()


class ActivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.password_hash=hash_password('test-password')

    def setUp(self):
        self.p=pending_tests.PendingDeviceTests();self.p.password_hash=self.password_hash
        if hasattr(self,'engine_override'):self.p.engine_override=self.engine_override
        self.p.setUp();self.f=self.p.f
        self.pending=self.p.begin().json();self.p.prove(self.pending)
        self.identifier=self.pending['pending_registration_id'];self.provider=FixtureProvider()
        self.service=DeviceActivationService(self.f.fixture.app.state.context)
        with self.f.sessions.begin() as db:
            student=db.get(Student,'DEVICE001')
            student.face_encoding=encrypt_encoding([0.0]*128,self.f.fixture.settings.biometric_key)
            student.biometric_status='active'
            pending=db.get(PendingDeviceRegistration,self.identifier)
            self.binding=ApprovalBinding(student.student_id,pending.auth_token_hash,self.identifier,
                pending.candidate_device_id,pending.public_key_fingerprint)
            db.add(FixtureRevision(revision_id='revision-1',student_id=student.student_id,
                template_hash=hashlib.sha256(student.face_encoding.encode()).hexdigest(),trusted=True))
            db.add(FixtureGrant(approval_id='grant-1',binding=json.dumps(self.binding.__dict__),revision_id='revision-1',result='PASS',
                verified_at=self.f.fixture.now,expires_at=self.f.fixture.now+timedelta(seconds=60)))
            db.add(FixtureResult(result_id='trusted-result-1',binding=json.dumps(self.binding.__dict__),revision_id='revision-1',
                face_verified=True,liveness_verified=True,classification='TRUSTED_SERVER_RESULT',
                verified_at=self.f.fixture.now,expires_at=self.f.fixture.now+timedelta(seconds=60)))
        self.original=self.slot_one()

    def tearDown(self):self.p.tearDown()

    def slot_one(self):
        with self.f.sessions() as db:
            row=db.get(RegisteredDevice,self.f.device_id)
            return {column.name:getattr(row,column.name) for column in RegisteredDevice.__table__.columns}

    def call(self,method,*args,student_id='DEVICE001',headers=None):
        with self.f.sessions() as db:
            student=db.get(Student,student_id)
            token=(headers or self.f.headers)['Authorization'].split()[1]
            auth=db.get(AuthSession,digest(token))
            try:
                with patch('modules.devices.activation_service.trusted_approval_provider',return_value=self.provider):
                    result=getattr(self.service,method)(db,student,auth,*args)
                db.commit();return result
            except DeviceRegistrationError:
                # The future router must preserve failure audit/consumed nonce.
                db.commit();raise

    def issue(self):return self.call('_issue_transaction',self.identifier,'grant-1')
    def signature(self,challenge,key=None):
        return base64.b64encode((key or self.p.key).sign(base64.b64decode(challenge['signing_payload']),ec.ECDSA(hashes.SHA256()))).decode()
    def confirm(self,challenge,**kwargs):
        return self.call('_confirm_transaction',kwargs.pop('pending_id',self.identifier),challenge['challenge_id'],
            kwargs.pop('approval_id','grant-1'),kwargs.pop('signature',self.signature(challenge)),**kwargs)
    def denied(self,code,operation):
        with self.assertRaises(DeviceRegistrationError) as raised:operation()
        self.assertEqual(raised.exception.code,code)
    def count(self,model):return self.p.count(model)

    def test_valid_atomic_activation_with_isolated_trusted_grant(self):
        challenge=self.issue();payload=json.loads(base64.b64decode(challenge['signing_payload']))
        self.assertEqual(payload['purpose'],'device_activation')
        self.assertEqual(payload['trusted_template_revision_id'],'revision-1')
        self.assertEqual(payload['public_key_fingerprint'],self.binding.public_key_fingerprint)
        self.assertEqual(self.issue()['challenge_id'],challenge['challenge_id'])
        result=self.confirm(challenge)
        self.assertEqual(result['device']['status'],'ACTIVE');self.assertEqual(result['device']['slot_number'],2)
        self.assertFalse(result['attendance_authorized']);self.assertEqual(self.count(Attendance),0)
        self.assertEqual(self.slot_one(),self.original)
        with self.f.sessions() as db:
            self.assertIsNotNone(db.get(FixtureGrant,'grant-1').consumed_at)
            self.assertEqual(db.get(PendingDeviceRegistration,self.identifier).status,'ACTIVATED')
            self.assertEqual(db.get(DeviceActivationChallenge,challenge['challenge_id']).result,'PASS')
            self.assertEqual(db.scalar(select(func.count()).select_from(DeviceActivationEvent).where(DeviceActivationEvent.result=='PASS')),1)

    def test_missing_and_untrusted_approvals_fail_closed(self):
        self.denied('BIOMETRIC_TRUST_REQUIRED',lambda:self.call('_issue_transaction',self.identifier,'missing'))
        for result in ('FAIL','COMPLETED_UNTRUSTED'):
            with self.f.sessions.begin() as db:db.get(FixtureGrant,'grant-1').result=result
            self.denied('BIOMETRIC_TRUST_REQUIRED',self.issue)
        self.assertEqual(self.count(RegisteredDevice),1);self.assertEqual(self.count(Attendance),0)

    def test_expired_reused_and_untrusted_template_approvals(self):
        for changes,code in [({'expires_at':self.f.fixture.now},'APPROVAL_EXPIRED'),
                ({'consumed_at':self.f.fixture.now},'APPROVAL_USED'),
                ({'verified_at':self.f.fixture.now-timedelta(seconds=61)},'APPROVAL_EXPIRED')]:
            with self.f.sessions.begin() as db:
                grant=db.get(FixtureGrant,'grant-1')
                grant.expires_at=self.f.fixture.now+timedelta(seconds=60);grant.consumed_at=None;grant.verified_at=self.f.fixture.now
                for key,value in changes.items():setattr(grant,key,value)
            self.denied(code,self.issue)
        with self.f.sessions.begin() as db:
            grant=db.get(FixtureGrant,'grant-1');grant.verified_at=self.f.fixture.now;grant.expires_at=self.f.fixture.now+timedelta(seconds=60);grant.consumed_at=None
            db.get(FixtureRevision,'revision-1').trusted=False
        self.denied('BIOMETRIC_TRUST_REQUIRED',self.issue)

    def test_every_approval_binding_field_is_validated(self):
        for field in self.binding.__dict__:
            with self.f.sessions.begin() as db:
                data=dict(self.binding.__dict__);data[field]=3 if field=='slot_number' else 'wrong'
                db.get(FixtureGrant,'grant-1').binding=json.dumps(data)
            self.denied('APPROVAL_MISMATCH',self.issue)
        self.assertEqual(self.count(RegisteredDevice),1)

    def test_wrong_student_or_new_login_cannot_consume_challenge(self):
        challenge=self.issue()
        other=self.f.fixture.login('DEVICE002')
        self.denied('PENDING_NOT_FOUND',lambda:self.confirm(challenge,student_id='DEVICE002',headers=other))
        another_login=self.f.fixture.login('DEVICE001')
        self.denied('PENDING_NOT_FOUND',lambda:self.confirm(challenge,headers=another_login))
        with self.f.sessions() as db:self.assertIsNone(db.get(DeviceActivationChallenge,challenge['challenge_id']).consumed_at)
        self.confirm(challenge)

    def test_invalid_signature_consumes_nonce_and_logs_failure(self):
        challenge=self.issue()
        bad=self.signature(challenge,ec.generate_private_key(ec.SECP256R1()))
        self.denied('INVALID_ACTIVATION_SIGNATURE',lambda:self.confirm(challenge,signature=bad))
        self.denied('ACTIVATION_REPLAYED',lambda:self.confirm(challenge))
        with self.f.sessions() as db:
            row=db.get(DeviceActivationChallenge,challenge['challenge_id'])
            self.assertIsNotNone(row.consumed_at);self.assertEqual(row.failure_code,'INVALID_ACTIVATION_SIGNATURE')
            self.assertIsNone(db.get(FixtureGrant,'grant-1').consumed_at)
        self.assertEqual(self.count(RegisteredDevice),1)

    def test_expired_and_replayed_activation_challenges(self):
        challenge=self.issue();self.f.fixture.now+=timedelta(seconds=61)
        self.denied('ACTIVATION_EXPIRED',lambda:self.confirm(challenge))
        self.denied('ACTIVATION_REPLAYED',lambda:self.confirm(challenge))
        self.assertEqual(self.count(RegisteredDevice),1)

    def test_revision_or_template_change_after_issuance_is_rejected(self):
        challenge=self.issue()
        with self.f.sessions.begin() as db:db.get(FixtureRevision,'revision-1').template_hash='changed'
        self.denied('BIOMETRIC_TRUST_REQUIRED',lambda:self.confirm(challenge))
        self.assertEqual(self.count(RegisteredDevice),1)

    def test_changed_candidate_or_approval_binding_after_issue(self):
        challenge=self.issue()
        with self.f.sessions.begin() as db:db.get(DeviceActivationChallenge,challenge['challenge_id']).public_key_fingerprint='wrong'
        self.denied('ACTIVATION_BINDING_MISMATCH',lambda:self.confirm(challenge))
        self.assertEqual(self.count(RegisteredDevice),1)

    def occupy_slot_two(self,slot_one_active=True):
        key=ec.generate_private_key(ec.SECP256R1())
        body=self.f.fixture.body(key);public,fingerprint=canonical_public_key(body['public_key_spki'])
        with self.f.sessions.begin() as db:
            if not slot_one_active:db.get(RegisteredDevice,self.f.device_id).status='INACTIVE'
            db.add(RegisteredDevice(device_id='occupied-tablet',student_id='DEVICE001',slot_number=2,
                public_key_spki=public,public_key_fingerprint=fingerprint,device_name='Other tablet',device_model='Fixture',
                platform='android',status='ACTIVE',registered_at=self.f.fixture.now))

    def test_both_slots_occupied_rejects_third_device(self):
        challenge=self.issue();self.occupy_slot_two()
        self.denied('DEVICE_LIMIT_REACHED',lambda:self.confirm(challenge))
        self.assertEqual(self.count(RegisteredDevice),2);self.assertEqual(self.slot_one(),self.original)

    def test_slot_two_occupied_never_becomes_replacement_shortcut(self):
        self.occupy_slot_two(slot_one_active=False)
        self.denied('REPLACEMENT_REQUIRED',self.issue)
        self.assertEqual(self.count(RegisteredDevice),2)

    def test_provider_consumption_rolls_back_with_failed_activation(self):
        challenge=self.issue()
        def broken(db,approval,now):
            FixtureProvider.consume(self.provider,db,approval,now)
            raise DeviceRegistrationError(409,'PROVIDER_CHANGED','Fixture rollback.')
        with patch.object(self.provider,'consume',side_effect=broken):
            self.denied('PROVIDER_CHANGED',lambda:self.confirm(challenge))
        with self.f.sessions() as db:
            self.assertIsNone(db.get(FixtureGrant,'grant-1').consumed_at)
            self.assertEqual(db.get(PendingDeviceRegistration,self.identifier).status,'KEY_PROVEN')
        self.assertEqual(self.count(RegisteredDevice),1)

    def test_approval_expiry_reuse_and_untrusted_result_are_rechecked_at_confirmation(self):
        for field,value,code in [('expires_at',self.f.fixture.now,'APPROVAL_EXPIRED'),
                ('consumed_at',self.f.fixture.now,'APPROVAL_USED'),('result','COMPLETED_UNTRUSTED','BIOMETRIC_TRUST_REQUIRED')]:
            with self.f.sessions.begin() as db:
                grant=db.get(FixtureGrant,'grant-1');grant.expires_at=self.f.fixture.now+timedelta(seconds=60)
                grant.consumed_at=None;grant.result='PASS'
            challenge=self.issue()
            with self.f.sessions.begin() as db:setattr(db.get(FixtureGrant,'grant-1'),field,value)
            self.denied(code,lambda:self.confirm(challenge))
        self.assertEqual(self.count(RegisteredDevice),1);self.assertEqual(self.count(Attendance),0)

    def test_only_key_proven_and_unexpired_candidates_are_eligible(self):
        with self.f.sessions.begin() as db:db.get(PendingDeviceRegistration,self.identifier).status='FAILED'
        self.denied('CANDIDATE_PROOF_REQUIRED',self.issue)
        with self.f.sessions.begin() as db:
            row=db.get(PendingDeviceRegistration,self.identifier);row.status='KEY_PROVEN';row.expires_at=self.f.fixture.now
        self.denied('PENDING_EXPIRED',self.issue)

    def test_wrong_pending_id_and_cross_operation_signature_are_rejected(self):
        challenge=self.issue()
        self.denied('PENDING_NOT_FOUND',lambda:self.confirm(challenge,pending_id='wrong-pending'))
        with self.f.sessions() as db:payload=db.get(PendingDeviceRegistration,self.identifier).signing_payload
        wrong=base64.b64encode(self.p.key.sign(payload.encode(),ec.ECDSA(hashes.SHA256()))).decode()
        self.denied('INVALID_ACTIVATION_SIGNATURE',lambda:self.confirm(challenge,signature=wrong))

    def test_trust_revision_switch_after_issuance_is_rejected(self):
        challenge=self.issue()
        with self.f.sessions.begin() as db:
            original=db.get(FixtureRevision,'revision-1')
            db.add(FixtureRevision(revision_id='revision-2',student_id=original.student_id,
                template_hash=original.template_hash,trusted=True))
            db.get(FixtureGrant,'grant-1').revision_id='revision-2'
        self.denied('APPROVAL_REVISION_CHANGED',lambda:self.confirm(challenge))
        self.assertEqual(self.count(RegisteredDevice),1)

    def test_real_provider_fails_closed_through_authenticated_public_routes(self):
        base='/api/v1/devices/pending-registrations/'+self.identifier
        response=self.f.client.post(base+'/activation-readiness',headers=self.f.headers,json={})
        self.assertEqual(response.status_code,503);self.assertEqual(response.json()['code'],'APPROVAL_UNAVAILABLE')
        response=self.f.client.post(base+'/activation-challenges',headers=self.f.headers,json={'approval_id':'grant-1'})
        self.assertEqual(response.status_code,503)
        self.assertEqual(self.f.client.post(base+'/activation-readiness',json={}).status_code,401)
        self.assertEqual(self.f.client.post(base+'/activation-readiness',headers=self.f.headers,json={'trusted':True}).status_code,422)
        self.assertEqual(self.count(RegisteredDevice),1);self.assertEqual(self.count(Attendance),0)
        self.assertEqual(self.slot_one(),self.original)

    def test_persisted_b3_test_id_cannot_be_relabelled_as_a_trusted_result(self):
        from modules.devices.biometric_models import DeviceBiometricSession
        with self.f.sessions.begin() as db:
            pending=db.get(PendingDeviceRegistration,self.identifier)
            db.add(DeviceBiometricSession(approval_id='trusted-result-1',pending_registration_id=self.identifier,
                student_id='DEVICE001',auth_token_hash=pending.auth_token_hash,candidate_device_id=pending.candidate_device_id,
                public_key_fingerprint=pending.public_key_fingerprint,slot_number=2,operation='enroll_second_device',
                template_binding='test-binding',stage='COMPLETED_UNTRUSTED',fingers=3,valid_frames=3,frame_count=4,frame_hashes='[]',
                created_at=self.f.fixture.now,expires_at=self.f.fixture.now+timedelta(seconds=60),completed_at=self.f.fixture.now))
        self.denied('BIOMETRIC_TRUST_REQUIRED',self.issue)
        self.assertEqual(self.count(RegisteredDevice),1);self.assertEqual(self.count(Attendance),0)

    def test_full_rest_flow_with_isolated_trusted_provider(self):
        base='/api/v1/devices/pending-registrations/'+self.identifier
        with patch('modules.devices.activation_service.trusted_approval_provider',return_value=self.provider):
            ready=self.f.client.post(base+'/activation-readiness',headers=self.f.headers,json={})
            self.assertEqual(ready.status_code,200,ready.text)
            issued=self.f.client.post(base+'/activation-challenges',headers=self.f.headers,json={'approval_id':ready.json()['approval_id']})
            self.assertEqual(issued.status_code,201,issued.text)
            challenge=issued.json()
            activated=self.f.client.post(base+'/activate',headers=self.f.headers,json={
                'challenge_id':challenge['challenge_id'],'approval_id':challenge['approval_id'],'signature':self.signature(challenge)})
            self.assertEqual(activated.status_code,200,activated.text)
            replay=self.f.client.post(base+'/activate',headers=self.f.headers,json={
                'challenge_id':challenge['challenge_id'],'approval_id':challenge['approval_id'],'signature':self.signature(challenge)})
            self.assertEqual(replay.json()['code'],'ACTIVATION_REPLAYED')
        status=self.f.client.get(base+'/activation-status',headers=self.f.headers)
        self.assertEqual(status.json()['status'],'ACTIVE');self.assertEqual(status.json()['active_count'],2)
        self.assertEqual(self.count(Attendance),0);self.assertEqual(self.slot_one(),self.original)

    def test_untrusted_or_mismatched_fresh_result_never_authorizes_activation(self):
        for field,value in [('classification','UNTRUSTED_TEST_RESULT'),('face_verified',False),('liveness_verified',False),('binding','{}')]:
            with self.f.sessions.begin() as db:
                row=db.get(FixtureResult,'trusted-result-1')
                row.classification='TRUSTED_SERVER_RESULT';row.face_verified=True;row.liveness_verified=True
                row.binding=json.dumps(self.binding.__dict__)
                setattr(row,field,value if field!='binding' else json.dumps({**self.binding.__dict__,'student_id':'wrong'}))
            self.denied('BIOMETRIC_TRUST_REQUIRED',self.issue)
        self.assertEqual(self.count(RegisteredDevice),1)


@unittest.skipUnless(os.getenv('ATTENDANCE_DEVICE_MYSQL_TESTS')=='1','Opt-in isolated MariaDB B4 races.')
class ActivationMariaDBTests(unittest.TestCase):
    def test_parallel_activation_is_single_use_and_preserves_slot_one(self):
        import mysql.connector
        settings=Settings();schema='attendance_b4_test_'+secrets.token_hex(6)
        control=mysql.connector.connect(host=settings.db_host,port=settings.db_port,user=settings.db_user,password=settings.db_password)
        harness=ActivationTests();created=False;engine=None
        try:
            with control.cursor() as c:c.execute('CREATE DATABASE `'+schema+'` CHARACTER SET utf8mb4')
            created=True;engine=make_engine(replace(settings,db_name=schema))
            harness.engine_override=engine;harness.password_hash=hash_password('test-password');harness.setUp()
            self.assertEqual(upgrade_activation_schema(engine)['created_tables'],[])
            base='/api/v1/devices/pending-registrations/'+harness.identifier
            headers=harness.f.headers
            def post(suffix,body,auth=None):
                return harness.f.client.post(base+suffix,headers=auth or headers,json=body)
            def proof(challenge,key=None):
                return {'approval_id':challenge['approval_id'],'challenge_id':challenge['challenge_id'],
                    'signature':harness.signature(challenge,key)}
            with patch('modules.devices.activation_service.trusted_approval_provider',return_value=harness.provider):
                ready=post('/activation-readiness',{});self.assertEqual(ready.status_code,200)
                first=post('/activation-challenges',{'approval_id':ready.json()['approval_id']}).json()
                # Repeated preparation is idempotent, not another registration.
                duplicate=harness.p.begin().json();self.assertEqual(duplicate['pending_registration_id'],harness.identifier)
                another_login=harness.f.fixture.login('DEVICE001')
                other_student=harness.f.fixture.login('DEVICE002')
                self.assertEqual(post('/activate',proof(first),another_login).status_code,404)
                self.assertEqual(post('/activate',proof(first),other_student).status_code,404)
                denied=post('/activate',proof(first,ec.generate_private_key(ec.SECP256R1())))
                self.assertEqual(denied.json()['code'],'INVALID_ACTIVATION_SIGNATURE')
                self.assertEqual(post('/activate',proof(first)).json()['code'],'ACTIVATION_REPLAYED')
                expired=post('/activation-challenges',{'approval_id':'grant-1'}).json()
                harness.f.fixture.now+=timedelta(seconds=61)
                self.assertEqual(post('/activate',proof(expired)).json()['code'],'ACTIVATION_EXPIRED')
                # Separate new trusted fixture evidence; never refresh/relabel old B3 results.
                with harness.f.sessions.begin() as db:
                    now=harness.f.fixture.now
                    db.add(FixtureResult(result_id='trusted-result-2',binding=json.dumps(harness.binding.__dict__),revision_id='revision-1',
                        face_verified=True,liveness_verified=True,classification='TRUSTED_SERVER_RESULT',verified_at=now,expires_at=now+timedelta(seconds=60)))
                    db.add(FixtureGrant(approval_id='grant-2',result_id='trusted-result-2',binding=json.dumps(harness.binding.__dict__),
                        revision_id='revision-1',result='PASS',verified_at=now,expires_at=now+timedelta(seconds=60)))
                ready=post('/activation-readiness',{});self.assertEqual(ready.json()['approval_id'],'grant-2')
                challenge=post('/activation-challenges',{'approval_id':'grant-2'}).json();body=proof(challenge)
                def activate(_):
                    with __import__('fastapi.testclient',fromlist=['TestClient']).TestClient(harness.f.fixture.app) as client:
                        response=client.post(base+'/activate',headers=headers,json=body)
                        return response.json()['device']['status'] if response.status_code==200 else response.json()['code']
                with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(activate,range(2)))
                self.assertEqual(sorted(results),['ACTIVATION_REPLAYED','ACTIVE'])
                self.assertEqual(harness.f.client.get('/api/v1/devices',headers=headers).json()['active_count'],2)
                self.assertEqual(harness.f.client.get(base+'/activation-status',headers=headers).json()['status'],'ACTIVE')
                third=harness.p.begin(body=harness.f.fixture.body(ec.generate_private_key(ec.SECP256R1())))
                self.assertEqual(third.json()['code'],'DEVICE_LIMIT_REACHED')
            self.assertEqual(harness.count(RegisteredDevice),2);self.assertEqual(harness.slot_one(),harness.original)
            self.assertEqual(harness.count(Attendance),0)
        finally:
            if hasattr(harness,'p'):harness.tearDown()
            elif engine:engine.dispose()
            if created:
                if not re.fullmatch('attendance_b4_test_[0-9a-f]{12}',schema):raise RuntimeError('Unsafe B4 cleanup')
                with control.cursor() as c:c.execute('DROP DATABASE `'+schema+'`')
            control.close()
