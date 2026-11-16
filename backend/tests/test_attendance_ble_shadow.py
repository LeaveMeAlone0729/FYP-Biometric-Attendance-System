"""Signed BLE and the real attendance routes against in-memory fixtures."""
import base64
import json
import re
import unittest
from datetime import timedelta

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

import test_classroom_attendance as attendance
from admin_testing import create_panel
from models import Attendance
from modules.classroom_ble.migration import upgrade
from modules.classroom_ble.models import BleChallenge
from modules.classroom_ble.policies import change
from modules.classroom_ble.router import router
from modules.classroom_ble.service import BleVerificationService
from modules.classroom_ble.shadow import OPERATION, recent_outcomes
from modules.devices.crypto import canonical_public_key
from modules.devices.models import RegisteredDevice
from modules.classroom_wifi.attendance import configure
from modules.classroom_wifi.policies import change as change_wifi

PATH = '/api/v1/classroom-ble'
UUID = 'b1ba7f4e-6931-49d5-99de-7e0caa159105'
WRONG_UUID = 'b1ba7f4e-6931-49d5-99de-7e0caa159106'


class AttendanceBleShadowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        attendance.ClassroomAttendanceTests.setUpClass()

    def setUp(self):
        self.classroom = attendance.ClassroomAttendanceTests()
        self.classroom.setUp()
        self.addCleanup(self.classroom.tearDown)
        self.f = self.classroom.f
        upgrade(self.f.engine)
        self.f.app.include_router(router)
        with self.f.sessions.begin() as db:
            for policy, room, uuid in [('beacon-a', 'A', UUID), ('beacon-b', 'B', WRONG_UUID)]:
                change(db, 'add', policy_id=policy, classroom=room, service_uuid=uuid,
                       actor='test', now=self.f.current)
                change(db, 'enable', policy_id=policy, actor='test', now=self.f.current)

    def start(self):
        attempt = self.f.start()
        proof = self.preflight_proof(attempt)
        wifi, receipt, _ = self.classroom.wifi(attempt, proof, preflight=True)
        self.assertEqual(wifi.json()['result'], 'PASS', wifi.text)
        ready = self.f.client.post('/api/v1/attendance/preflight', headers=self.f.headers,
            json=dict(attendance_challenge_id=attempt, challenge_id=proof['challenge_id'],
                      signature=self.classroom.a.signature(proof), classroom_wifi_proof_id=receipt['challenge_id']))
        self.assertEqual(ready.status_code, 200, ready.text)
        return attempt, proof['challenge_id']

    def preflight_proof(self, attempt):
        proof = self.f.client.post('/api/v1/attendance/preflight-challenges', headers=self.f.headers,
            json=dict(attendance_challenge_id=attempt, public_key_fingerprint=self.f.device_fingerprint))
        self.assertEqual(proof.status_code, 201, proof.text)
        return proof.json()

    def issue(self, attempt, proof, *, headers=None, **overrides):
        return self.f.client.post(PATH + '/challenges', headers=headers or self.f.headers, json={
            **dict(classroom_id='A', public_key_fingerprint=self.f.device_fingerprint,
                   attendance_attempt_id=attempt, preflight_proof_id=proof), **overrides})

    def evidence(self, **overrides):
        start = BleVerificationService(self.f.app.state.context).ms(self.f.current)
        return dict(scan_status='COMPLETE', bluetooth_enabled=True, scan_permission='GRANTED',
                    connect_permission='GRANTED', location_permission='PRECISE_GRANTED', location_enabled=True,
                    scan_started_at_ms=start, scan_completed_at_ms=start + 8000, scan_duration_ms=8000,
                    beacons=[dict(service_uuid=UUID, samples=[dict(offset_us=i * 1000000, rssi_dbm=-55)
                                                             for i in range(5)])]) | overrides

    def body(self, challenge, evidence):
        raw = json.dumps(evidence).encode()
        signature = self.f.device_key.sign(base64.b64decode(challenge['signing_payload']) + b'\n' + raw,
                                           ec.ECDSA(hashes.SHA256()))
        return dict(challenge_id=challenge['challenge_id'], evidence_payload=base64.b64encode(raw).decode(),
                    signature=base64.b64encode(signature).decode())

    def confirm(self, body, headers=None):
        response = self.f.client.post(PATH + '/verifications', headers=headers or self.f.headers, json=body)
        self.assertEqual(self.classroom.a.count(Attendance), 0)
        return response

    def complete(self, attempt, *, wifi_bssid=None, source=None):
        self.f.face(attempt)
        proof = self.classroom.a.issue(attempt).json()
        for i in range(2):
            self.classroom.a.frame(attempt, proof, image=f'frame-{i}'.encode())
        overrides = {'bssid': wifi_bssid} if wifi_bssid else {}
        _, wifi, _ = self.classroom.wifi(attempt, proof, evidence=self.classroom.evidence(**overrides))
        return self.classroom.final(attempt, proof, wifi['challenge_id'], source=source)

    def test_pass_binds_to_preflight_and_never_writes_attendance(self):
        attempt, proof = self.start()
        issued = self.issue(attempt, proof)
        self.assertEqual(issued.status_code, 201, issued.text)
        ch = issued.json()
        self.assertEqual(self.issue(attempt, proof).json()['code'], 'BLE_SHADOW_ALREADY_STARTED')
        signed = json.loads(base64.b64decode(ch['signing_payload']))
        self.assertEqual((signed['attendance_attempt_id'], signed['preflight_proof_id'],
                          signed['classroom_id'], signed['operation']), (attempt, proof, 'A', OPERATION))
        evidence = self.evidence()
        self.f.current += timedelta(seconds=8)
        body = self.body(ch, evidence)
        result = self.confirm(body).json()
        self.assertEqual(result['reason_code'], 'BLE_APPROVED', result)
        self.assertFalse(result['attendance_authorized'])
        self.assertEqual(self.confirm(body).json()['code'], 'BLE_CHALLENGE_REPLAYED')
        response = self.complete(attempt)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.classroom.a.count(Attendance), 1)
        self.assertEqual(self.f.client.post('/attendance/start', headers=self.f.headers,
                                           json={'pin': '123456'}).status_code, 409)
        self.assertEqual(self.classroom.a.count(Attendance), 1)

    def test_missing_wrong_weak_stale_future_and_unavailable_are_non_authorizing(self):
        cases = ['BLE_BEACON_NOT_FOUND', 'wrong UUID', 'BLE_SIGNAL_WEAK', 'BLE_INSUFFICIENT_SAMPLES',
                 'BLE_EVIDENCE_STALE', 'BLE_EVIDENCE_FUTURE', 'BLUETOOTH_OFF']
        for case in cases:
            with self.subTest(case=case):
                attempt, proof = self.start()
                ch = self.issue(attempt, proof).json()
                evidence = self.evidence()
                samples = evidence['beacons'][0]['samples']
                if case in ('BLE_BEACON_NOT_FOUND', 'BLUETOOTH_OFF'):
                    evidence['beacons'] = []
                    evidence['bluetooth_enabled'] = case != 'BLUETOOTH_OFF'
                elif case == 'wrong UUID':
                    evidence['beacons'][0]['service_uuid'] = WRONG_UUID
                elif case == 'BLE_SIGNAL_WEAK':
                    for sample in samples:
                        sample['rssi_dbm'] = -95
                elif case == 'BLE_INSUFFICIENT_SAMPLES':
                    samples.pop()
                else:
                    offset = -1 if case == 'BLE_EVIDENCE_STALE' else 2001
                    evidence['scan_started_at_ms'] += offset
                    evidence['scan_completed_at_ms'] += offset
                self.f.current += timedelta(seconds=8)
                result = self.confirm(self.body(ch, evidence)).json()
                self.assertEqual(result['reason_code'], 'BLE_BEACON_NOT_FOUND' if case == 'wrong UUID' else case)
                self.assertFalse(result['attendance_authorized'])
        response = self.complete(attempt)
        self.assertEqual(response.status_code, 200, response.text)

    def test_missing_beacon_does_not_block_and_pass_cannot_bypass_wifi_or_network(self):
        for result, overrides in [('BLE_APPROVED', {'wifi_bssid': 'c6:0b:cc:3b:1b:1e'}),
                                  ('BLE_APPROVED', {'source': '198.51.100.1'}), ('BLE_BEACON_NOT_FOUND', {})]:
            attempt, proof = self.start()
            ch = self.issue(attempt, proof).json()
            evidence = self.evidence()
            if result == 'BLE_BEACON_NOT_FOUND':
                evidence['beacons'] = []
            self.f.current += timedelta(seconds=8)
            self.assertEqual(self.confirm(self.body(ch, evidence)).json()['reason_code'], result)
            response = self.complete(attempt, **overrides)
            self.assertEqual(response.status_code, 403 if overrides else 200, response.text)
            self.assertEqual(self.classroom.a.count(Attendance), 0 if overrides else 1)

    def test_binding_rejects_wrong_identity_classroom_device_attempt_and_signature(self):
        first, proof = self.start()
        foreign = self.f.client.post('/login', json={'student_id': 'TEST002', 'password': 'test-password'}).json()
        headers = {'Authorization': 'Bearer ' + foreign['access_token']}
        self.assertEqual(self.issue(first, proof, headers=headers).json()['code'], 'BLE_SHADOW_BINDING_MISMATCH')
        second_login = self.f.client.post('/login', json={'student_id': 'TEST001', 'password': 'test-password'}).json()
        login_headers = {'Authorization': 'Bearer ' + second_login['access_token']}
        self.assertEqual(self.issue(first, proof, headers=login_headers).json()['code'], 'BLE_SHADOW_BINDING_MISMATCH')
        key = ec.generate_private_key(ec.SECP256R1())
        public, fingerprint = canonical_public_key(base64.b64encode(key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).decode())
        with self.f.sessions.begin() as db:
            db.add(RegisteredDevice(device_id='second-fixture-device', student_id='TEST001', slot_number=2,
                public_key_spki=public, public_key_fingerprint=fingerprint, device_name='Fixture',
                device_model='Fixture', platform='android', status='ACTIVE', registered_at=self.f.current))
        for overrides in [{'classroom_id': 'B'}, {'public_key_fingerprint': fingerprint}]:
            self.assertEqual(self.issue(first, proof, **overrides).json()['code'], 'BLE_SHADOW_BINDING_MISMATCH')
        first_ch = self.issue(first, proof).json()
        first_evidence = self.evidence()
        second, new_proof = self.start()
        self.assertEqual(self.issue(second, proof).json()['code'], 'BLE_SHADOW_BINDING_MISMATCH')
        second_ch = self.issue(second, new_proof).json()
        self.f.current += timedelta(seconds=8)
        first_body = self.body(first_ch, first_evidence)
        self.assertEqual(self.confirm(first_body, headers).json()['code'], 'BLE_CHALLENGE_NOT_FOUND')
        self.assertEqual(self.confirm(first_body).json()['code'], 'BLE_SHADOW_ATTEMPT_ENDED')
        self.assertEqual(self.confirm(first_body | {'challenge_id': second_ch['challenge_id']}).json()['code'],
                         'INVALID_DEVICE_SIGNATURE')

    def test_ble_pass_cannot_substitute_for_face_or_final_device_proof(self):
        attempt, proof = self.start()
        challenge = self.issue(attempt, proof).json()
        evidence = self.evidence()
        self.f.current += timedelta(seconds=8)
        self.assertEqual(self.confirm(self.body(challenge, evidence)).json()['reason_code'], 'BLE_APPROVED')
        self.assertGreaterEqual(self.classroom.a.frame(attempt).status_code, 400)
        self.assertEqual(self.classroom.a.count(Attendance), 0)

    def test_wifi_only_classroom_records_not_configured_without_starting_scan(self):
        with self.f.sessions.begin() as db:
            change(db, 'disable', policy_id='beacon-a', actor='test', now=self.f.current)
        attempt, proof = self.start()
        response = self.issue(attempt, proof)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()['code'], 'NO_ENABLED_BLE_POLICY')
        self.assertEqual(self.classroom.a.count(BleChallenge), 0)
        with self.f.sessions() as db:
            row = next(recent_outcomes(db, self.f.current))
        self.assertEqual((row['result'], row['reason']), ('NOT CHECKED', 'NO_ENABLED_BLE_POLICY'))
        self.assertIn('NO_ENABLED_BLE_POLICY', self.admin_page())
        self.assertEqual(self.complete(attempt).status_code, 200)

    def test_wrong_classroom_requires_wifi_before_beacon_can_be_not_detected(self):
        with self.f.sessions.begin() as db:
            configure(db, session_id=self.classroom.session_id, classroom_id='B', now=self.f.current)
        attempt = self.f.start()
        proof = self.preflight_proof(attempt)
        wifi, _, _ = self.classroom.wifi(attempt, proof, preflight=True)
        self.assertEqual(wifi.json()['reason_code'], 'NO_ENABLED_CLASSROOM_POLICY')
        denied = self.issue(attempt, proof['challenge_id'], classroom_id='B')
        self.assertEqual(denied.json()['code'], 'BLE_SHADOW_BINDING_MISMATCH')
        with self.f.sessions() as db:
            row = next(recent_outcomes(db, self.f.current))
        self.assertEqual((row['result'], row['reason']), ('NOT CHECKED', 'NO_ENABLED_CLASSROOM_POLICY'))
        self.assertIn('NO_ENABLED_CLASSROOM_POLICY', self.admin_page())
        self.assertEqual(self.classroom.a.count(BleChallenge), 0)
        with self.f.sessions.begin() as db:
            change_wifi(db, 'add', policy_id='b-home', classroom='B', access_point='d8:42:a1:9e:de:2f',
                        network_name='Home', actor='test', now=self.f.current)
        self.f.current += timedelta(seconds=1)
        attempt, proof_id = self.start()
        issued = self.issue(attempt, proof_id, classroom_id='B')
        self.assertEqual(issued.status_code, 201, issued.text)
        evidence = self.evidence()  # A's UUID can never satisfy B's policy.
        self.f.current += timedelta(seconds=8)
        response = self.confirm(self.body(issued.json(), evidence))
        self.assertEqual(response.json()['reason_code'], 'BLE_BEACON_NOT_FOUND')
        self.assertFalse(response.json()['attendance_authorized'])
        self.assertIn('BLE_BEACON_NOT_FOUND', self.admin_page())
        self.assertEqual(self.complete(attempt).status_code, 200)

    def test_admin_monitor_uses_real_attempts_and_redacts_evidence(self):
        for mode in ('not checked', 'dropped', 'missing', 'pass'):
            attempt, proof = self.start()
            if mode != 'not checked':
                issued = self.issue(attempt, proof)
                self.assertEqual(issued.status_code, 201, issued.text)
                if mode != 'dropped':
                    evidence = self.evidence()
                    if mode == 'missing':
                        evidence['beacons'] = []
                    self.f.current += timedelta(seconds=8)
                    self.assertEqual(self.confirm(self.body(issued.json(), evidence)).status_code, 200)
        with self.f.sessions() as db:
            self.assertEqual([row['result'] for row in recent_outcomes(db, self.f.current)],
                             ['PASS', 'FAIL', 'UNAVAILABLE', 'NOT CHECKED'])
        page = self.admin_page()
        for token in ('Attendance BLE shadow results', 'BLE_APPROVED', 'BLE_BEACON_NOT_FOUND',
                      'BLE_RESULT_NOT_RECEIVED', 'NOT CHECKED'):
            self.assertIn(token, page)
        for private in ('TEST001', attempt, proof, 'signing_payload', 'auth_session_hash'):
            self.assertNotIn(private, page)

    def admin_page(self):
        origin = 'http://127.0.0.1:8003'
        app = create_panel(self.f.engine, username='operator', password_hash=self.classroom.password_hash,
                           ready=lambda: {'classroom_wifi': True}, now=lambda: self.f.current,
                           database_port=3306, simulation_only=False)
        with TestClient(app, base_url=origin, client=('127.0.0.1', 3210), follow_redirects=False) as client:
            self.assertEqual(client.get('/ble').status_code, 303)
            csrf = re.search(r'name="csrf" value="([^"]+)"', client.get('/login').text).group(1)
            self.assertEqual(client.post('/login', headers={'Origin': origin}, data=dict(
                csrf=csrf, username='operator', password='test-password')).status_code, 303)
            page = client.get('/ble')
            self.assertEqual(page.status_code, 200, page.text)
            return page.text
