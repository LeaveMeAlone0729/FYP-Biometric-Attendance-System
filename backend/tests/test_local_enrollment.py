"""Local enrollment repair, using synthetic in-memory data and real P-256 proofs."""
import base64
import hashlib
import io
import json
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from test_staff_portal import fixture_engine, NOW
from models import AuthSession, Student
from modules.devices import local_demo
from modules.devices.models import RegisteredDevice, DeviceRegistrationEvent
from modules.devices.pending_models import PendingDeviceRegistration, DeviceEnrollmentEvent
from modules.devices.biometric_models import DeviceBiometricSession, DeviceBiometricEvent
from modules.devices.activation_models import DeviceActivationChallenge, DeviceActivationEvent
from modules.devices.management_models import MANAGEMENT_TABLES, EnrollmentRevision, DeviceBiometricAuthorization
from modules.devices.pending_service import PendingEnrollmentService
from modules.devices.biometric_service import DeviceBiometricService
from modules.devices.activation_service import DeviceActivationService
from modules.devices.management_approval import LocalDeviceApprovalProvider
from modules.devices.service import DeviceRegistrationError
from modules.biometrics.templates import encrypt_encoding
from modules.biometrics.enrollment_policy import check_first_enrollment, record_first_enrollment
from local_account_verification import AccountVerificationRejected, record_account
from local_enrollment import configure_files, provision_account


def public_key(key):
    return base64.b64encode(key.public_key().public_bytes(serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo)).decode()


def signature(key, payload):
    return base64.b64encode(key.sign(payload.encode(), ec.ECDSA(hashes.SHA256()))).decode()


class SyntheticBio:
    fingers = 1
    def decode(self, raw):
        return np.full((3, 3, 3), raw[0], dtype=np.uint8)
    def guided_face(self, image):
        return np.zeros(128)
    face = guided_face
    def distance(self, first, second):
        return 0.0
    def hand(self, image):
        return self.fingers


class LocalEnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.engine = fixture_engine()
        for model in (RegisteredDevice, DeviceRegistrationEvent, PendingDeviceRegistration, DeviceEnrollmentEvent,
                      DeviceBiometricSession, DeviceBiometricEvent):
            model.__table__.create(self.engine)
        for table in MANAGEMENT_TABLES:
            table.create(self.engine)
        for model in (DeviceActivationChallenge, DeviceActivationEvent):
            model.__table__.create(self.engine)
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.operator = b't' * 32
        self.settings = SimpleNamespace(biometric_key=Fernet.generate_key().decode(), face_threshold=.45,
            challenge_seconds=90, timezone='Asia/Kuala_Lumpur', fyp_account_bound_enrollment=True)
        self.now = NOW + timedelta(seconds=10)
        self.context = SimpleNamespace(settings=self.settings, now=lambda: self.now, bio=SyntheticBio())
        self.db = Session(self.engine, info={local_demo.CREDENTIAL: self.operator, local_demo.ACCOUNT_POLICY: True,
                                           'fyp_account_bound_enrollment': True})
        self.student = self.db.get(Student, 'S001')
        self.student.face_encoding = encrypt_encoding(np.zeros(128), self.settings.biometric_key)
        self.student.biometric_status = 'active'
        first = ec.generate_private_key(ec.SECP256R1())
        first_public = public_key(first)
        from modules.devices.crypto import canonical_public_key
        self.db.add(RegisteredDevice(device_id='first-device', student_id='S001', slot_number=1,
            public_key_spki=first_public, public_key_fingerprint=canonical_public_key(first_public)[1],
            device_name='First device', device_model='Synthetic phone', platform='android', status='ACTIVE', registered_at=NOW))
        self.auth = AuthSession(token_hash='offline-auth', student_id='S001', expires_at=NOW + timedelta(hours=8))
        self.db.add(self.auth)
        self.db.commit()
        self.pending = PendingEnrollmentService(self.context)
        self.bio = DeviceBiometricService(self.context)
        self.activation = DeviceActivationService(self.context)
        self.frame = 1

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def complete_scan(self):
        data = SimpleNamespace(public_key_spki=public_key(self.key), device_name='Second device', device_model='Synthetic phone')
        pending = self.pending.begin_pending(self.db, self.student, self.auth, data)
        payload = base64.b64decode(pending['signing_payload']).decode()
        self.pending.proof(self.db, self.student, self.auth, pending['pending_registration_id'], signature(self.key, payload))
        result = self.bio.create(self.db, self.student, self.auth, pending['pending_registration_id'])
        scan_id = result['approval_id']
        def frame():
            self.frame += 1
            return SimpleNamespace(file=io.BytesIO(bytes([self.frame])))
        result = self.bio.face(self.db, self.student, self.auth, scan_id, frame())
        self.context.bio.fingers = result['fingers']
        for _ in range(3):
            result = self.bio.liveness(self.db, self.student, self.auth, scan_id, frame())
        self.assertEqual(result['stage'], 'COMPLETED_UNTRUSTED')
        self.db.commit()
        return pending['pending_registration_id'], scan_id

    def test_setup_then_fresh_scan_activates_slot_two_without_changing_slot_one(self):
        pending_id, setup_scan = self.complete_scan()
        with self.assertRaises(DeviceRegistrationError) as rejected:
            self.activation.readiness(self.db, self.student, self.auth, pending_id)
        self.assertEqual(rejected.exception.code, 'LOCAL_FYP_ACCOUNT_VERIFICATION_REQUIRED')
        self.db.rollback()
        record_account(self.db, 'S001', setup_scan, self.now)
        self.db.commit()
        self.assertEqual(self.db.scalar(select(func.count()).select_from(DeviceBiometricAuthorization)), 0)
        self.assertEqual(self.db.get(RegisteredDevice, 'first-device').status, 'ACTIVE')
        self.db.get(PendingDeviceRegistration, pending_id).status = 'CANCELLED'
        self.db.commit()
        self.now += timedelta(seconds=1)
        pending_id, new_scan = self.complete_scan()
        self.assertNotEqual(setup_scan, new_scan)
        ready = self.activation.readiness(self.db, self.student, self.auth, pending_id)
        challenge = self.activation.issue(self.db, self.student, self.auth, pending_id, ready['approval_id'])
        payload = base64.b64decode(challenge['signing_payload']).decode()
        result = self.activation.confirm(self.db, self.student, self.auth, pending_id,
            challenge['challenge_id'], ready['approval_id'], signature(self.key, payload))
        self.db.commit()
        self.assertEqual(result['device']['status'], 'ACTIVE')
        self.assertEqual(result['device']['slot_number'], 2)
        self.assertEqual(self.db.get(RegisteredDevice, 'first-device').status, 'ACTIVE')
        self.assertEqual(self.db.scalar(select(func.count()).select_from(RegisteredDevice)), 2)

    def test_fractional_setup_timestamp_is_stable_in_datetime_zero_storage(self):
        self.now = self.now.replace(microsecond=900000)
        _, scan = self.complete_scan()
        identifier = record_account(self.db, 'S001', scan, self.now)
        self.db.commit()
        self.db.expire_all()
        revision = self.db.get(EnrollmentRevision, identifier)
        self.assertEqual(revision.verified_at, self.now.replace(microsecond=0))
        self.assertTrue(local_demo.verified_account(self.db, revision))
        self.assertEqual(self.db.scalar(select(func.count()).select_from(RegisteredDevice)), 1)

    def test_expired_scan_cannot_create_enrollment(self):
        _, scan = self.complete_scan()
        self.now += timedelta(minutes=2)
        with self.assertRaises(AccountVerificationRejected):
            record_account(self.db, 'S001', scan, self.now)
        self.db.rollback()
        self.assertEqual(self.db.scalar(select(func.count()).select_from(EnrollmentRevision)), 0)

    def test_account_setup_requires_explicit_local_profile(self):
        _, scan = self.complete_scan()
        self.db.info[local_demo.ACCOUNT_POLICY] = False
        with self.assertRaises(AccountVerificationRejected):
            record_account(self.db, 'S001', scan, self.now)

    def test_wrong_account_and_replayed_setup_are_rejected(self):
        _, scan = self.complete_scan()
        with self.assertRaises(AccountVerificationRejected):
            record_account(self.db, 'S002', scan, self.now)
        self.db.rollback()
        record_account(self.db, 'S001', scan, self.now)
        self.db.commit()
        with self.assertRaises(AccountVerificationRejected):
            record_account(self.db, 'S001', scan, self.now)
        self.db.rollback()
        self.assertEqual(self.db.scalar(select(func.count()).select_from(EnrollmentRevision)), 1)

    def test_different_operator_key_and_tampered_evidence_are_not_trusted(self):
        _, scan = self.complete_scan()
        record_account(self.db, 'S001', scan, self.now)
        self.db.commit()
        provider = LocalDeviceApprovalProvider()
        self.assertIsNotNone(provider.current_template_revision(self.db, 'S001', self.now))
        self.db.info[local_demo.CREDENTIAL] = b'x' * 32
        self.assertIsNone(provider.current_template_revision(self.db, 'S001', self.now))
        self.db.info[local_demo.CREDENTIAL] = self.operator
        revision = self.db.scalar(select(EnrollmentRevision))
        revision.evidence_reference = revision.evidence_reference[:-1] + ('1' if revision.evidence_reference[-1] != '1' else '2')
        self.db.flush()
        self.assertIsNone(provider.current_template_revision(self.db, 'S001', self.now))

    def test_provisioned_new_account_gets_trust_on_first_face_enrollment(self):
        student = self.db.get(Student, 'S002')
        student.biometric_status = 'not_registered'
        auth = AuthSession(token_hash='new-account-auth', student_id='S002', expires_at=self.now + timedelta(hours=1))
        self.db.add(auth)
        self.db.flush()
        with self.assertRaises(Exception):
            check_first_enrollment(self.context, self.db, student, auth)
        self.assertTrue(provision_account(self.db, student, self.now))
        self.assertFalse(provision_account(self.db, student, self.now))
        school = check_first_enrollment(self.context, self.db, student, auth)
        student.face_encoding = encrypt_encoding(np.zeros(128), self.settings.biometric_key)
        student.biometric_status = 'active'
        record_first_enrollment(self.context, self.db, student, auth, school)
        self.db.commit()
        revision = self.db.scalar(select(EnrollmentRevision).where(EnrollmentRevision.student_id == 'S002'))
        self.assertEqual(revision.assurance_level, 'ACCOUNT_BOUND_FYP')
        self.assertEqual(revision.template_hash, hashlib.sha256(student.face_encoding.encode()).hexdigest())
        self.assertIsNotNone(LocalDeviceApprovalProvider().current_template_revision(self.db, 'S002', self.now))


class LocalProfileTests(unittest.TestCase):
    def profile(self, folder):
        profile = dict(db_host='127.0.0.1', db_port=3306, db_name='own_fyp', db_user='local_app',
            db_password='offline-test-password', biometric_key=Fernet.generate_key().decode(),
            fyp_account_bound_enrollment=False, ble_executable='')
        identity = dict(account_bound_fyp=False, schema='own_fyp', account='local_app', identity_marker='unchanged')
        (folder/'settings.json').write_text(json.dumps(profile))
        (folder/'identity.json').write_text(json.dumps(identity))
        return profile, identity

    def test_enable_backs_up_profile_preserves_database_key_and_reuses_credential(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            profile, identity = self.profile(folder)
            backup = configure_files(folder, identity)
            self.assertTrue((backup/'settings.json').is_file())
            expected = dict(profile, fyp_account_bound_enrollment=True)
            self.assertEqual(json.loads((folder/'settings.json').read_text()), expected)
            expected_identity = dict(identity, account_bound_fyp=True)
            self.assertEqual(json.loads((folder/'identity.json').read_text()), expected_identity)
            key = (folder/'local-enrollment.key').read_bytes()
            self.assertEqual(len(key), 32)
            self.assertIsNone(configure_files(folder, expected_identity))
            self.assertEqual((folder/'local-enrollment.key').read_bytes(), key)

    def test_wrong_identity_is_rejected_without_changing_any_configuration(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            profile, identity = self.profile(folder)
            before = (folder/'settings.json').read_bytes()
            with self.assertRaises(ValueError):
                configure_files(folder, dict(identity, schema='different_database'))
            self.assertEqual((folder/'settings.json').read_bytes(), before)
            self.assertFalse((folder/'local-enrollment.key').exists())

    def test_interrupted_enable_restores_original_profile_and_pin(self):
        import local_enrollment
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            _, identity = self.profile(folder)
            before = {name: (folder/name).read_bytes() for name in ('settings.json', 'identity.json')}
            original = local_enrollment.write_private
            failed = False
            def fail_once(path, content):
                nonlocal failed
                if path.name == 'identity.json' and not failed:
                    failed = True
                    raise OSError('Synthetic interruption')
                original(path, content)
            with patch('local_enrollment.write_private', side_effect=fail_once):
                with self.assertRaises(OSError):
                    configure_files(folder, identity)
            self.assertEqual({name: (folder/name).read_bytes() for name in before}, before)
            self.assertFalse((folder/'local-enrollment.key').exists())


if __name__ == '__main__':
    unittest.main()
