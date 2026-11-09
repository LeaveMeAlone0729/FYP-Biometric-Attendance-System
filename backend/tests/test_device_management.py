"""Self-service REST flow with local provider, synthetic identities and real P-256.

No provider monkeypatch or production trust seed. The provenance fixture is usable
only by explicitly tagged in-memory SQLite Sessions, never by the runtime app.
"""
import base64
import hashlib
import sys
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select, func
from models import Student, Attendance
from modules.devices.models import RegisteredDevice
from modules.devices.pending_models import PendingDeviceRegistration
from modules.devices.management_models import EnrollmentRevision, DeviceBiometricAuthorization
from modules.devices.approval_provider import trusted_approval_provider
from modules.devices import local_demo
from security import hash_password
from verify_enrollment_identity import (
    VerificationRejected, encode_evidence, record_local_demo, record_verified_enrollment, supervised_evidence,
)
import test_device_biometrics as biometric
import test_device_replacement as replacement


def synthetic_enrollment(f):
    """Explicit test-only fixture; cannot operate on a server/production DB."""
    engine = f.sessions.kw['bind']
    assert engine.dialect.name == 'sqlite' and engine.url.database in (None, '', ':memory:')
    f.sessions.configure(info={'synthetic_enrollment_fixture': True})
    f.fixture.app.state.context.sessions.configure(info={'synthetic_enrollment_fixture': True})
    with f.sessions.begin() as db:
        student = db.get(Student, 'DEVICE001')
        db.add(EnrollmentRevision(revision_id='synthetic-enrollment-only', student_id=student.student_id,
            template_hash=hashlib.sha256(student.face_encoding.encode()).hexdigest(),
            provenance='synthetic_fixture', evidence_reference='IN-MEMORY TEST IDENTITY; NOT INSTITUTIONAL TRUST',
            verified_at=f.fixture.now))


class ManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.password_hash = hash_password('test-password')

    def setUp(self):
        self.h = biometric.DeviceBiometricTests(); self.h.password_hash = self.password_hash
        if hasattr(self, 'engine_override'): self.h.engine_override = self.engine_override
        self.h.setUp(); self.addCleanup(self.h.tearDown)
        self.f = self.h.f; self.pending = self.h.pending
        self.original = self.rows()

    def rows(self, f=None):
        with (f or self.f).sessions() as db:
            return {d.device_id: {c.name: getattr(d, c.name) for c in RegisteredDevice.__table__.columns}
                    for d in db.scalars(select(RegisteredDevice))}

    def post(self, suffix, body, f=None, pending=None, headers=None):
        f = f or self.f; pending = pending or self.pending
        return f.client.post('/api/v1/devices/pending-registrations/'+pending['pending_registration_id']+suffix,
                             headers=headers or f.headers, json=body)

    def ready(self):
        _, raw = self.h.complete()
        self.assertEqual(raw.json()['stage'], 'COMPLETED_UNTRUSTED')
        self.assertFalse(raw.json()['trusted'])
        response = self.post('/activation-readiness', {})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotEqual(response.json()['biometric_result_id'], raw.json()['approval_id'])
        return response.json()

    def issue(self, ready):
        response = self.post('/activation-challenges', {'approval_id': ready['approval_id']})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def confirm(self, ready, challenge, key=None, **kwargs):
        signature = (key or self.h.p.key).sign(base64.b64decode(challenge['signing_payload']), ec.ECDSA(hashes.SHA256()))
        return self.post('/activate', {'approval_id': ready['approval_id'], 'challenge_id': challenge['challenge_id'],
            'signature': base64.b64encode(signature).decode()}, **kwargs)

    def no_change(self):
        self.assertEqual(self.rows(), self.original)
        with self.f.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Attendance)), 0)

    def test_slot2_full_flow_with_local_provider_and_independent_keys(self):
        synthetic_enrollment(self.f)
        ready = self.ready(); challenge = self.issue(ready)
        self.assertEqual(type(trusted_approval_provider()).__name__, 'LocalDeviceApprovalProvider')
        result = self.confirm(ready, challenge); self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['device']['status'], 'ACTIVE')
        after = self.rows(); self.assertEqual(after[self.f.device_id], self.original[self.f.device_id])
        self.assertEqual(len(after), 2)
        new = after[self.pending['candidate_device_id']]
        for fingerprint, key in [(new['public_key_fingerprint'], self.h.p.key), (self.f.fingerprint, self.f.key)]:
            verification = self.f.issue(fingerprint=fingerprint)
            proof = self.f.confirm(verification.json(), key=key)
            self.assertEqual(proof.json()['result'], 'PASS')
            self.assertFalse(proof.json()['attendance_authorized'])
        self.assertEqual(self.confirm(ready, challenge).json()['code'], 'ACTIVATION_REPLAYED')
        with self.f.sessions() as db:
            grant = db.get(DeviceBiometricAuthorization, ready['approval_id'])
            self.assertIsNotNone(grant.consumed_at)
            self.assertEqual(db.scalar(select(func.count()).select_from(Attendance)), 0)
        self.demo_evidence = dict(operation='slot2', active_count=2,
            both_keys_verified=True, slot1_unchanged=True, approval_consumed=True,
            attendance_inserted=0, synthetic_identity=True, institutional_identity_verified=False)

    def test_self_enrolled_face_does_not_get_provenance_or_authorization(self):
        # Exercise genuine first-enrollment API for this synthetic account, not
        # merely a hand-written active status. No existing real template changes.
        with self.f.sessions.begin() as db:
            student = db.get(Student, 'DEVICE001')
            student.face_encoding = None; student.biometric_status = 'not_registered'; student.consent_at = None
        enrollment = self.f.client.post('/register-face', headers=self.f.headers,
            data={'consent': 'true'}, files={'file': ('fixture.jpg', b'enrollment', 'image/jpeg')})
        self.assertEqual(enrollment.status_code, 200, enrollment.text)
        self.h.complete()
        response = self.post('/activation-readiness', {})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'BIOMETRIC_TRUST_REQUIRED')
        with self.f.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(EnrollmentRevision)), 0)
            self.assertEqual(db.scalar(select(func.count()).select_from(DeviceBiometricAuthorization)), 0)
        self.no_change()
        self.demo_evidence = dict(operation='unverified_enrollment', result='BLOCKED',
            code='BIOMETRIC_TRUST_REQUIRED', active_count=1, attendance_inserted=0)

    def test_synthetic_provenance_without_isolated_session_marker_is_not_trust(self):
        synthetic_enrollment(self.f)
        self.f.fixture.app.state.context.sessions.configure(info={})
        self.h.complete()
        self.assertEqual(self.post('/activation-readiness', {}).json()['code'], 'BIOMETRIC_TRUST_REQUIRED')
        self.no_change()
        # Even a tagged Session may not use synthetic trust in MySQL or a file DB.
        from unittest.mock import Mock
        from types import SimpleNamespace
        from modules.devices.management_approval import LocalDeviceApprovalProvider
        row = SimpleNamespace(revision_id='fixture-only', invalidated_at=None, verified_at=self.f.fixture.now,
                              evidence_reference='isolated fixture', provenance='synthetic_fixture')
        for dialect, database in [('mysql', 'testschema'), ('sqlite', 'test.sqlite')]:
            db = Mock(); db.info = {'synthetic_enrollment_fixture': True}
            db.get_bind.return_value.dialect.name = dialect
            db.get_bind.return_value.url.database = database
            self.assertFalse(LocalDeviceApprovalProvider()._valid_revision(db, row, self.f.fixture.now))
            db.get.assert_not_called()

    def test_trust_added_after_completed_scan_cannot_relabel_old_result(self):
        self.h.complete(); synthetic_enrollment(self.f)
        self.assertEqual(self.post('/activation-readiness', {}).json()['code'], 'FRESH_BIOMETRIC_PROOF_REQUIRED')
        self.no_change()

    def test_signed_supervised_reverification_requires_a_new_scan_and_preserves_slot_one(self):
        scan_id, _ = self.h.complete()
        fixture = self.f.fixture
        signer = Ed25519PrivateKey.generate()
        with self.f.sessions.begin() as db:
            original_face = db.get(Student, 'DEVICE001').face_encoding
            evidence = supervised_evidence(db, 'DEVICE001', scan_id, 'TEST-CASE-1', fixture.now, fixture.settings)
            payload = encode_evidence(evidence)
            signature = signer.sign(payload)
            revision_id = record_verified_enrollment(db, payload, signature, signer.public_key(), fixture.now, fixture.settings)
            revision = db.get(EnrollmentRevision, revision_id)
            self.assertEqual(revision.provenance, 'external_verified')
            self.assertEqual(revision.assurance_level, 'INSTITUTION_VERIFIED')
            self.assertEqual(revision.verified_at, fixture.now)
            self.assertEqual(db.get(Student, 'DEVICE001').face_encoding, original_face)

        self.no_change()
        with self.f.sessions.begin() as db, self.assertRaisesRegex(VerificationRejected, 'history already exists'):
            record_verified_enrollment(db, payload, signature, signer.public_key(), fixture.now, fixture.settings)
        self.assertEqual(self.post('/activation-readiness', {}).json()['code'], 'FRESH_BIOMETRIC_PROOF_REQUIRED')
        fixture.now += timedelta(seconds=91)
        ready = self.ready()
        challenge = self.issue(ready)
        result = self.confirm(ready, challenge)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['device']['slot_number'], 2)
        self.assertEqual(self.rows()[self.f.device_id], self.original[self.f.device_id])
        with self.f.sessions() as db:
            self.assertEqual(db.get(Student, 'DEVICE001').face_encoding, original_face)
            self.assertEqual(db.scalar(select(func.count()).select_from(Attendance)), 0)

    def test_supervised_evidence_rejects_untrusted_signature_stale_scan_and_changed_template(self):
        scan_id, _ = self.h.complete()
        fixture = self.f.fixture
        signer = Ed25519PrivateKey.generate()
        with self.f.sessions.begin() as db:
            evidence = supervised_evidence(db, 'DEVICE001', scan_id, 'TEST-CASE-2', fixture.now, fixture.settings)
            payload = encode_evidence(evidence)
            signature = signer.sign(payload)
            with self.assertRaisesRegex(VerificationRejected, 'pinned institutional verifier'):
                record_verified_enrollment(db, payload, signature, Ed25519PrivateKey.generate().public_key(), fixture.now, fixture.settings)
            changed = encode_evidence({**evidence, 'candidate_key_fingerprint': 'different-key'})
            with self.assertRaisesRegex(VerificationRejected, 'differs from the current server evidence'):
                record_verified_enrollment(db, changed, signer.sign(changed), signer.public_key(), fixture.now, fixture.settings)
            with self.assertRaisesRegex(VerificationRejected, 'fresh completed Slot 2 scan'):
                record_verified_enrollment(db, payload, signature, signer.public_key(), fixture.now + timedelta(minutes=10), fixture.settings)
            student = db.get(Student, 'DEVICE001')
            student.face_encoding += 'changed'
            with self.assertRaisesRegex(VerificationRejected, 'fresh completed Slot 2 scan'):
                record_verified_enrollment(db, payload, signature, signer.public_key(), fixture.now, fixture.settings)
            self.assertEqual(db.scalar(select(func.count()).select_from(EnrollmentRevision)), 0)
        self.no_change()

    def test_missing_biometric_proof_is_rejected_even_with_provenance(self):
        synthetic_enrollment(self.f)
        self.assertEqual(self.post('/activation-readiness', {}).json()['code'], 'FRESH_BIOMETRIC_PROOF_REQUIRED')
        self.no_change()

    @patch.object(local_demo, 'DEMO_STUDENT', 'DEVICE001')
    def test_local_demo_activates_only_bound_slot2_and_is_disabled_without_credential(self):
        fixture = self.f.fixture
        credential = {local_demo.CREDENTIAL: b'\x8f' * 32}
        fixture.app.state.sessions.configure(info=credential)
        self.f.sessions.configure(info=credential)
        fixture.now += timedelta(minutes=6)
        self.pending = self.h.pending = self.h.p.begin().json()
        self.assertTrue(self.pending['candidate_device_id'].startswith(local_demo.PREFIX))
        self.h.p.prove(self.pending)
        scan, _ = self.h.complete()
        self.assertEqual(self.post('/activation-readiness', {}).json()['code'], 'LOCAL_DEMO_EVIDENCE_REQUIRED')
        with self.f.sessions.begin() as db:
            revision_id = record_local_demo(db, scan, fixture.now, fixture.settings)
            revision = db.get(EnrollmentRevision, revision_id)
            self.assertEqual(revision.assurance_level, 'UNVERIFIED')
            self.assertTrue(revision.evidence_reference.startswith('LOCAL_FYP_DEMO|'))
            self.assertEqual(local_demo.verified_fingerprint(db, revision), self.pending['public_key_fingerprint'])
            revision.evidence_reference += 'tamper'
            self.assertIsNone(local_demo.verified_fingerprint(db, revision))
            revision.evidence_reference = revision.evidence_reference.removesuffix('tamper')
        self.no_change()
        self.assertEqual(self.post('/activation-readiness', {}).json()['code'], 'FRESH_BIOMETRIC_PROOF_REQUIRED')
        fixture.now += timedelta(seconds=91)
        ready = self.ready()
        challenge = self.issue(ready)
        response = self.confirm(ready, challenge)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['device']['device_name'].startswith('[LOCAL FYP DEMO]'))
        self.assertEqual(self.rows()[self.f.device_id], self.original[self.f.device_id])
        fingerprint = self.pending['public_key_fingerprint']
        proof = self.f.issue(fingerprint=fingerprint)
        self.assertEqual(self.f.confirm(proof.json(), key=self.h.p.key).json()['result'], 'PASS')
        fixture.app.state.sessions.configure(info={})
        self.assertEqual(self.f.issue(fingerprint=fingerprint).json()['code'], 'LOCAL_DEMO_DEVICE_DISABLED')
        self.assertEqual(self.f.issue(fingerprint=self.f.fingerprint).status_code, 201)

    def test_wrong_face_cannot_issue_authorization(self):
        synthetic_enrollment(self.f)
        identifier = self.h.create().json()['approval_id']
        self.assertEqual(self.h.frame(identifier, b'other-face').json()['code'], 'FACE_NOT_MATCHED')
        self.assertEqual(self.post('/activation-readiness', {}).json()['code'], 'FRESH_BIOMETRIC_PROOF_REQUIRED')
        self.no_change()

    def test_wrong_student_session_and_client_pass_are_rejected(self):
        synthetic_enrollment(self.f); ready = self.ready(); challenge = self.issue(ready)
        other = self.f.fixture.login('DEVICE002')
        self.assertEqual(self.confirm(ready, challenge, headers=other).status_code, 404)
        new_login = self.f.fixture.login('DEVICE001')
        self.assertEqual(self.confirm(ready, challenge, headers=new_login).status_code, 404)
        self.assertEqual(self.post('/activation-readiness', {'trusted': True}).status_code, 422)
        self.no_change()

    def test_forged_device_identity_and_wrong_operation_are_rejected(self):
        synthetic_enrollment(self.f); ready = self.ready(); challenge = self.issue(ready)
        self.assertEqual(self.post('/activation-challenges', {'approval_id': ready['approval_id'], 'device_id': 'forged'}).status_code, 422)
        with self.f.sessions.begin() as db:
            row = db.get(PendingDeviceRegistration, self.pending['pending_registration_id'])
            row.candidate_device_id = 'forged'
        self.assertEqual(self.confirm(ready, challenge).json()['code'], 'ACTIVATION_BINDING_MISMATCH')
        self.no_change()

    def test_wrong_operation_in_approval_binding_fails(self):
        import json
        synthetic_enrollment(self.f); ready = self.ready()
        with self.f.sessions.begin() as db:
            grant = db.get(DeviceBiometricAuthorization, ready['approval_id'])
            data = json.loads(grant.binding); data['operation'] = 'replace_device'; grant.binding = json.dumps(data)
        self.assertEqual(self.post('/activation-challenges', {'approval_id': ready['approval_id']}).json()['code'], 'APPROVAL_MISMATCH')
        self.no_change()

    def test_invalid_signature_consumes_activation_challenge(self):
        synthetic_enrollment(self.f); ready = self.ready(); challenge = self.issue(ready)
        self.assertEqual(self.confirm(ready, challenge, key=self.f.key).json()['code'], 'INVALID_ACTIVATION_SIGNATURE')
        self.assertEqual(self.confirm(ready, challenge).json()['code'], 'ACTIVATION_REPLAYED')
        self.no_change()

    def test_expired_grant_and_challenge_cannot_activate(self):
        synthetic_enrollment(self.f); ready = self.ready(); challenge = self.issue(ready)
        self.f.fixture.now += timedelta(seconds=61)
        self.assertEqual(self.confirm(ready, challenge).status_code, 410)
        self.no_change()

    def test_invalidated_or_changed_template_during_scan_cannot_get_grant(self):
        synthetic_enrollment(self.f)
        identifier, _ = self.h.face()
        with self.f.sessions.begin() as db:
            db.get(EnrollmentRevision, 'synthetic-enrollment-only').invalidated_at = self.f.fixture.now
        for index in range(3): self.h.frame(identifier, ('live-'+str(index)).encode(), 'liveness/frame')
        self.assertEqual(self.post('/activation-readiness', {}).json()['code'], 'BIOMETRIC_TRUST_REQUIRED')
        self.no_change()

    def test_face_deletion_and_reenrollment_stay_blocked(self):
        synthetic_enrollment(self.f)
        self.assertEqual(self.f.client.delete('/biometrics', headers=self.f.headers).status_code, 404)
        response = self.f.client.post('/register-face', headers=self.f.headers,
            data={'consent': 'true'}, files={'file': ('test.jpg', b'other-face', 'image/jpeg')})
        self.assertEqual(response.status_code, 409)
        self.no_change()

    def test_third_device_and_initial_api_shortcut_remain_blocked(self):
        self.test_slot2_full_flow_with_local_provider_and_independent_keys()
        self.assertEqual(self.h.p.begin().json()['code'], 'DEVICE_LIMIT_REACHED')
        response = self.f.fixture.begin()
        self.assertEqual(response.json()['code'], 'DEVICE_ALREADY_REGISTERED')

    def test_storage_missing_fails_closed_without_breaking_raw_biometric_checks(self):
        from modules.devices.management_models import MANAGEMENT_TABLES
        engine = self.f.sessions.kw['bind']
        self.assertEqual(engine.dialect.name, 'sqlite')
        for table in reversed(MANAGEMENT_TABLES): table.drop(engine)
        _, raw = self.h.complete()
        self.assertEqual(raw.json()['stage'], 'COMPLETED_UNTRUSTED')
        response = self.post('/activation-readiness', {})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['code'], 'APPROVAL_UNAVAILABLE')
        self.no_change()

    def test_microsecond_clock_progress_does_not_lose_genuine_completion(self):
        synthetic_enrollment(self.f)
        def advancing_clock():
            self.f.fixture.now += timedelta(microseconds=10)
            return self.f.fixture.now
        self.f.fixture.app.state.context.now = advancing_clock
        ready = self.ready()
        self.assertEqual(self.confirm(ready, self.issue(ready)).status_code, 200)

    def test_failed_insert_rolls_back_local_approval_consumption(self):
        from sqlalchemy import event
        from sqlalchemy.orm import Session
        from sqlalchemy.exc import IntegrityError
        synthetic_enrollment(self.f); ready = self.ready(); challenge = self.issue(ready)
        def refuse_candidate(db, *args):
            if any(isinstance(row, RegisteredDevice) for row in db.new):
                raise IntegrityError('isolated candidate insertion failure', {}, Exception('fixture'))
        event.listen(Session, 'before_flush', refuse_candidate)
        try:
            response = self.confirm(ready, challenge)
            self.assertEqual(response.status_code, 409)
        finally:
            event.remove(Session, 'before_flush', refuse_candidate)
        with self.f.sessions() as db:
            self.assertIsNone(db.get(DeviceBiometricAuthorization, ready['approval_id']).consumed_at)
        self.no_change()

    def test_migration_rejects_production_endpoint_before_connecting(self):
        from unittest.mock import Mock
        from sqlalchemy.engine import URL
        from modules.devices.management_migration import upgrade_management_schema
        engine = Mock(); engine.dialect.name = 'mysql'
        engine.url = URL.create('mysql+mysqlconnector', host='127.0.0.1', port=3306,
                                database='attendance_proposal_xampp')
        with self.assertRaises(RuntimeError): upgrade_management_schema(engine)
        engine.connect.assert_not_called()

    def test_schema_compiles_for_mysql_and_runtime_cannot_write_enrollment_trust(self):
        from sqlalchemy.dialects import mysql
        from sqlalchemy.schema import CreateTable
        from modules.devices.management_models import MANAGEMENT_TABLES
        from production_guard import required_grants
        for table in MANAGEMENT_TABLES:
            sql = str(CreateTable(table).compile(dialect=mysql.dialect()))
            self.assertIn('ENGINE=InnoDB', sql)
        grants = required_grants()
        self.assertEqual(grants['device_enrollment_revisions'], {('SELECT', None)})
        self.assertIn(('UPDATE', 'consumed_at'), grants['device_biometric_authorizations'])

    def replacement(self, slot):
        h = replacement.ReplacementTests(); h.password_hash = self.password_hash
        h.setUp(); self.addCleanup(h.tearDown)
        pending = h.prepare(slot); synthetic_enrollment(h.f)
        bio = biometric.DeviceBiometricTests(); bio.f = h.f; bio.p = h.h.p; bio.pending = pending
        bio.complete()
        ready = h.post('/activation-readiness', {}).json()
        challenge = h.post('/activation-challenges', {'approval_id': ready['approval_id']}).json()
        signature = h.h.signature(challenge)
        result = h.post('/activate', {'approval_id': ready['approval_id'], 'challenge_id': challenge['challenge_id'], 'signature': signature})
        self.assertEqual(result.status_code, 200, result.text)
        after = h.rows(); old = h.h.binding.replaced_device_id
        self.assertEqual(after[old]['status'], 'REVOKED')
        new = after[pending['candidate_device_id']]; self.assertEqual(new['status'], 'ACTIVE')
        for identifier, row in h.before.items():
            if identifier != old: self.assertEqual(after[identifier], row)
        self.assertNotEqual(h.f.issue(fingerprint=h.before[old]['public_key_fingerprint']).status_code, 201)
        verify = h.f.issue(fingerprint=new['public_key_fingerprint'])
        self.assertEqual(h.f.confirm(verify.json(), key=h.h.p.key).json()['result'], 'PASS')
        self.assertEqual(h.h.count(Attendance), 0)
        self.demo_evidence = dict(operation='replacement', slot=slot, old_device_revoked=True,
            candidate_key_verified=True, unaffected_slot_preserved=True,
            attendance_inserted=0, synthetic_identity=True, institutional_identity_verified=False)

    def test_local_slot1_replacement_revokes_old_key_preserves_slot2(self): self.replacement(1)
    def test_local_slot2_replacement_revokes_old_key_preserves_slot1(self): self.replacement(2)


if __name__ == '__main__': unittest.main()
