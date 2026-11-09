"""FYP account assurance through real REST; deterministic inference, disposable keys."""
import base64
import hashlib
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dataclasses import replace
from sqlalchemy import select, func
from models import Student, Attendance
from modules.devices.management_models import SchoolProvisionedAccount, EnrollmentRevision, DeviceBiometricAuthorization
from modules.devices.approval_provider import trusted_approval_provider
from modules.devices.models import RegisteredDevice
import test_device_management as management
import test_device_replacement as replacement
import test_device_biometrics as biometric
from security import hash_password


def prepare_account(f, identifier='DEVICE001', *, school=True):
    context = f.fixture.app.state.context
    context.settings = replace(context.settings, demo_mode=False, fyp_account_bound_enrollment=True)
    context.sessions.configure(info={'fyp_account_bound_enrollment': True})
    with f.sessions.begin() as db:
        student = db.get(Student, identifier)
        student.face_encoding = None
        student.biometric_status = 'not_registered'
        student.consent_at = None
        if school:
            db.add(SchoolProvisionedAccount(student_id=identifier,
                provisioning_reference='SYNTHETIC-SCHOOL-ROSTER-'+identifier,
                provisioned_at=f.fixture.now))


def enroll(f, headers=None, **data):
    return f.client.post('/register-face', headers=headers if headers is not None else f.headers,
        data={'consent': 'true', **data}, files={'file': ('fixture.jpg', b'enrollment', 'image/jpeg')})


class AccountBoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.password_hash = hash_password('test-password')

    def setUp(self):
        self.m = management.ManagementTests(); self.m.password_hash = self.password_hash
        if hasattr(self, 'engine_override'): self.m.engine_override = self.engine_override
        self.m.setUp(); self.addCleanup(self.m.doCleanups)
        self.f = self.m.f
        if hasattr(self, 'configure_runtime'): self.configure_runtime(self.f)

    def enrolled(self):
        prepare_account(self.f)
        self.assertEqual(self.f.fixture.login('DEVICE001')['Authorization'][:7], 'Bearer ')
        response = enroll(self.f)
        self.assertEqual(response.status_code, 200, response.text)
        with self.f.sessions() as db:
            row = db.scalar(select(EnrollmentRevision))
            student = db.get(Student, 'DEVICE001')
            self.assertEqual(row.assurance_level, 'ACCOUNT_BOUND_FYP')
            self.assertEqual(row.provenance, 'account_bound_fyp')
            self.assertEqual(row.student_id, 'DEVICE001')
            self.assertEqual(row.template_hash, hashlib.sha256(student.face_encoding.encode()).hexdigest())
        return response

    def test_first_enrollment_login_and_immutable_id(self):
        self.enrolled()
        self.assertEqual(enroll(self.f).status_code, 409)
        self.assertEqual(self.f.client.delete('/biometrics', headers=self.f.headers).status_code, 404)
        self.assertEqual(self.f.client.patch('/me', headers=self.f.headers, json={'student_id':'DEVICE002'}).status_code, 405)
        with self.f.sessions() as db:
            self.assertIsNone(db.get(Student,'DEVICE002').face_encoding)
            self.assertEqual(db.scalar(select(func.count()).select_from(EnrollmentRevision)), 1)

    def test_unauthenticated_and_wrong_student_enrollment(self):
        prepare_account(self.f)
        self.assertEqual(enroll(self.f, headers={}).status_code, 401)
        self.assertEqual(enroll(self.f, student_id='DEVICE002').status_code, 422)
        other = self.f.fixture.login('DEVICE002')
        self.assertEqual(enroll(self.f, headers=other).status_code, 403)
        self.assertEqual(enroll(self.f, assurance_level='INSTITUTION_VERIFIED').status_code, 422)
        with self.f.sessions() as db:
            self.assertIsNone(db.get(Student,'DEVICE001').face_encoding)
            self.assertEqual(db.scalar(select(func.count()).select_from(EnrollmentRevision)), 0)

    def test_unattested_and_public_self_registered_account_cannot_qualify(self):
        prepare_account(self.f, school=False)
        self.assertEqual(enroll(self.f).status_code, 403)
        context=self.f.fixture.app.state.context
        context.settings=replace(context.settings,demo_mode=True)
        response = self.f.client.post('/register', json={'student_id':'FORGED001','group_id':1,
            'name':'Forged','email':'forged@example.test','password':'test-password'})
        self.assertEqual(response.status_code, 403)

    def test_provenance_storage_failure_rolls_back_first_enrollment(self):
        from unittest.mock import patch
        from sqlalchemy.orm import Session
        from sqlalchemy.exc import IntegrityError
        prepare_account(self.f)
        original=Session.flush
        def fail(db,*args,**kwargs):
            if any(isinstance(row,EnrollmentRevision) for row in db.new):
                raise IntegrityError('synthetic enrollment persistence failure',{},Exception('test only'))
            return original(db,*args,**kwargs)
        # A transport/server error must never return a successful enrollment.
        with patch.object(Session,'flush',fail):
            self.assertEqual(enroll(self.f).status_code,503)
        with self.f.sessions() as db:
            self.assertIsNone(db.get(Student,'DEVICE001').face_encoding)
            self.assertEqual(db.scalar(select(func.count()).select_from(EnrollmentRevision)),0)

    def test_legacy_template_not_upgraded(self):
        context=self.f.fixture.app.state.context
        context.settings=replace(context.settings, fyp_account_bound_enrollment=True)
        context.sessions.configure(info={'fyp_account_bound_enrollment':True})
        with self.f.sessions.begin() as db:
            db.add(SchoolProvisionedAccount(student_id='DEVICE001',provisioning_reference='TEST-ONLY',provisioned_at=self.f.fixture.now))
        self.assertEqual(enroll(self.f).status_code,409)
        self.m.h.complete()
        self.assertEqual(self.m.post('/activation-readiness',{}).json()['code'],'BIOMETRIC_TRUST_REQUIRED')
        with self.f.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(EnrollmentRevision)),0)

    def test_slot2_account_bound_policy_full_flow_and_replay(self):
        self.enrolled()
        ready=self.m.ready();challenge=self.m.issue(ready)
        self.assertEqual(self.m.confirm(ready,challenge).status_code,200)
        self.assertEqual(self.m.confirm(ready,challenge).json()['code'],'ACTIVATION_REPLAYED')
        rows=self.m.rows()
        self.assertEqual(rows[self.f.device_id],self.m.original[self.f.device_id])
        self.assertEqual(len(rows),2)
        listing=self.f.client.get('/api/v1/devices',headers=self.f.headers).json()
        self.assertEqual(listing['active_count'],2)
        with self.f.sessions() as db:self.assertEqual(db.scalar(select(func.count()).select_from(Attendance)),0)

    def test_policy_disabled_after_enrollment_blocks_grant(self):
        self.enrolled()
        self.f.fixture.app.state.context.sessions.configure(info={'fyp_account_bound_enrollment':False})
        self.m.h.complete()
        self.assertEqual(self.m.post('/activation-readiness',{}).json()['code'],'BIOMETRIC_TRUST_REQUIRED')
        self.m.no_change()

    def test_wrong_face_liveness_and_signature_never_authorize(self):
        self.enrolled()
        identifier=self.m.h.create().json()['approval_id']
        self.assertEqual(self.m.h.frame(identifier,b'other-face').json()['code'],'FACE_NOT_MATCHED')
        identifier,response=self.m.h.face()
        self.f.fixture.app.state.context.bio.gesture=0
        response=self.m.h.frame(identifier,b'wrong-gesture','liveness/frame').json()
        self.assertEqual(response['valid_frames'],0)
        self.assertEqual(self.m.post('/activation-readiness',{}).json()['code'],'FRESH_BIOMETRIC_PROOF_REQUIRED')
        self.f.fixture.app.state.context.bio.gesture=response['fingers']
        for i in range(3): self.m.h.frame(identifier,('fresh'+str(i)).encode(),'liveness/frame')
        ready=self.m.post('/activation-readiness',{}).json();challenge=self.m.issue(ready)
        from cryptography.hazmat.primitives.asymmetric import ec
        self.assertEqual(self.m.confirm(ready,challenge,key=ec.generate_private_key(ec.SECP256R1())).status_code,403)
        self.assertNotEqual(self.m.confirm(ready,challenge).status_code,200)
        self.m.no_change()

    def test_enrollment_expiry_rolls_back_template_and_revision(self):
        from datetime import timedelta
        prepare_account(self.f)
        original=self.f.fixture.app.state.context.bio.face
        def slow(image):
            self.f.fixture.now += timedelta(hours=9)
            return original(image)
        self.f.fixture.app.state.context.bio.face=slow
        self.assertEqual(enroll(self.f).status_code,401)
        with self.f.sessions() as db:
            self.assertIsNone(db.get(Student,'DEVICE001').face_encoding)
            self.assertEqual(db.scalar(select(func.count()).select_from(EnrollmentRevision)),0)

    def replacement(self,slot):
        h=replacement.ReplacementTests();h.password_hash=self.password_hash
        if hasattr(self,'replacement_engine_override'):h.engine_override=self.replacement_engine_override
        elif hasattr(self,'engine_override'):h.engine_override=self.engine_override
        h.setUp();self.addCleanup(h.tearDown)
        if hasattr(self, 'configure_runtime'): self.configure_runtime(h.f)
        prepare_account(h.f)
        self.assertEqual(enroll(h.f).status_code,200)
        pending=h.prepare(slot)
        bio=biometric.DeviceBiometricTests();bio.f=h.f;bio.p=h.h.p;bio.pending=pending;bio.complete()
        ready=h.post('/activation-readiness',{}).json()
        challenge=h.post('/activation-challenges',{'approval_id':ready['approval_id']}).json()
        body={'approval_id':ready['approval_id'],'challenge_id':challenge['challenge_id'],'signature':h.h.signature(challenge)}
        result=h.post('/activate',body);self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(h.post('/activate',body).json()['code'],'ACTIVATION_REPLAYED')
        after=h.rows();old=h.h.binding.replaced_device_id
        self.assertEqual(after[old]['status'],'REVOKED')
        new=after[pending['candidate_device_id']];self.assertEqual(new['status'],'ACTIVE')
        for identifier,row in h.before.items():
            if identifier!=old:self.assertEqual(after[identifier],row)
        self.assertNotEqual(h.f.issue(fingerprint=h.before[old]['public_key_fingerprint']).status_code,201)
        proof=h.f.issue(fingerprint=new['public_key_fingerprint'])
        self.assertEqual(h.f.confirm(proof.json(),key=h.h.p.key).json()['result'],'PASS')
        self.assertEqual(h.h.count(Attendance),0)

    def test_account_bound_slot1_replacement(self):self.replacement(1)
    def test_account_bound_slot2_replacement(self):self.replacement(2)


if __name__=='__main__':unittest.main()
