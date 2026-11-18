"""Opt-in diagnostic composition with real signatures and no attendance writes."""
import base64
import json
import re
import unittest
from dataclasses import replace
from datetime import timedelta

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import select

import test_classroom_attendance as classroom
from admin_testing import create_panel
from models import Attendance, Challenge, ClassSession, VerificationAttempt
from modules.classroom_ble.migration import upgrade
from modules.classroom_ble.models import BleChallenge
from modules.classroom_ble.policies import change
from modules.classroom_ble.router import router as ble_router
from modules.classroom_ble.service import BleVerificationService
from modules.classroom_ble.diagnostic_mode import router, recent_test_outcomes
from modules.classroom_wifi.models import SessionClassroom
from modules.networks.models import NetworkPolicy

PATH = '/api/v1/network-ble-tests'
UUID = 'b1ba7f4e-6931-49d5-99de-7e0caa159105'
OTHER = 'b1ba7f4e-6931-49d5-99de-7e0caa159106'


class NetworkBleTestModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        classroom.ClassroomAttendanceTests.setUpClass()

    def setUp(self):
        self.c = classroom.ClassroomAttendanceTests()
        self.c.setUp()
        self.addCleanup(self.c.tearDown)
        self.f = self.c.f
        self.context = self.f.app.state.context
        self.context.settings = replace(self.context.settings, network_ble_test_mode=True)
        upgrade(self.f.engine)
        self.f.app.include_router(ble_router)
        self.f.app.include_router(router)
        with self.f.sessions.begin() as db:
            change(db, 'add', policy_id='test-beacon', classroom='A', service_uuid=UUID,
                   actor='synthetic', now=self.f.current)
            change(db, 'enable', policy_id='test-beacon', actor='synthetic', now=self.f.current)

    def tearDown(self):
        for model in (Attendance, Challenge, VerificationAttempt):
            self.assertEqual(self.c.a.count(model), 0, model.__name__)

    def start(self, **overrides):
        return self.f.client.post(PATH + '/start', headers=self.f.headers, json={
            'session_id': self.c.session_id, 'pin': '123456',
            'public_key_fingerprint': self.f.device_fingerprint, **overrides})

    def evidence(self):
        start = BleVerificationService(self.context).ms(self.f.current)
        return dict(scan_status='COMPLETE', bluetooth_enabled=True, scan_permission='GRANTED',
            connect_permission='GRANTED', location_permission='PRECISE_GRANTED', location_enabled=True,
            scan_started_at_ms=start, scan_completed_at_ms=start + 8000, scan_duration_ms=8000,
            beacons=[dict(service_uuid=UUID, samples=[dict(offset_us=i * 1000000, rssi_dbm=-55)
                                                     for i in range(5)])])

    def sign(self, challenge, evidence, key=None):
        raw = json.dumps(evidence).encode()
        signature = (key or self.f.device_key).sign(base64.b64decode(challenge['signing_payload']) + b'\n' + raw,
                                                   ec.ECDSA(hashes.SHA256()))
        return dict(challenge_id=challenge['challenge_id'], evidence_payload=base64.b64encode(raw).decode(),
                    signature=base64.b64encode(signature).decode())

    def ready(self):
        response = self.start()
        self.assertEqual(response.status_code, 200, response.text)
        begin = response.json()
        body = dict(test_id=begin['test_id'], wifi=self.sign(begin['wifi'], self.c.evidence()),
                    ble=self.sign(begin['ble'], self.evidence()))
        self.f.current += timedelta(seconds=8)
        return begin, body

    def finish(self, body, client=None, headers=None):
        response = (client or self.f.client).post(PATH + '/finish', headers=headers or self.f.headers, json=body)
        self.assertEqual(self.c.a.count(Attendance), 0)
        return response

    def test_disabled_by_default_and_routes_require_authentication(self):
        from config import Settings
        self.assertFalse(replace(Settings(), network_ble_test_mode=False).network_ble_test_mode)
        self.assertEqual(self.f.client.get(PATH + '/sessions').status_code, 401)
        self.context.settings = replace(self.context.settings, network_ble_test_mode=False)
        self.assertEqual(self.start().status_code, 404)
        self.assertEqual(self.f.client.get(PATH + '/sessions', headers=self.f.headers).status_code, 404)
        self.assertEqual(self.c.a.count(BleChallenge), 0)

    def test_valid_session_pin_wifi_device_and_beacon_return_only_test_pass(self):
        listing = self.f.client.get(PATH + '/sessions', headers=self.f.headers).json()
        self.assertIn(self.c.session_id, [row['session_id'] for row in listing['sessions']])
        begin, body = self.ready()
        response = self.finish(body)
        self.assertEqual(response.json()['test_result'], 'PASS', response.text)
        self.assertTrue(response.json()['diagnostic_test'])
        self.assertFalse(response.json()['attendance_authorized'])
        with self.f.sessions() as db:
            audit = list(recent_test_outcomes(db))
        self.assertEqual(audit[0]['result'], 'TEST_PASS')
        self.assertEqual(audit[0]['session'], self.c.session_id)
        attempted_writer = self.f.client.post('/api/v1/attendance/device-challenges', headers=self.f.headers,
            json={'attendance_challenge_id': begin['test_id'], 'public_key_fingerprint': self.f.device_fingerprint})
        self.assertGreaterEqual(attempted_writer.status_code, 400)

    def test_missing_wrong_weak_insufficient_and_bluetooth_off_fail(self):
        for kind, expected in [('absent', 'BLE_BEACON_NOT_FOUND'), ('wrong', 'BLE_BEACON_NOT_FOUND'),
                ('weak', 'BLE_SIGNAL_WEAK'), ('insufficient', 'BLE_INSUFFICIENT_SAMPLES'), ('off', 'BLUETOOTH_OFF')]:
            with self.subTest(kind=kind):
                begin = self.start().json()
                wifi = self.sign(begin['wifi'], self.c.evidence())
                evidence = self.evidence()
                if kind in ('absent', 'off'):
                    evidence['beacons'] = []
                    evidence['bluetooth_enabled'] = kind != 'off'
                elif kind == 'wrong':
                    evidence['beacons'][0]['service_uuid'] = OTHER
                elif kind == 'weak':
                    for sample in evidence['beacons'][0]['samples']:
                        sample['rssi_dbm'] = -99
                else:
                    evidence['beacons'][0]['samples'].pop()
                self.f.current += timedelta(seconds=8)
                response = self.finish(dict(test_id=begin['test_id'], wifi=wifi,
                                             ble=self.sign(begin['ble'], evidence)))
                self.assertEqual((response.json()['test_result'], response.json()['reason_code']), ('FAIL', expected))

    def test_wifi_failure_and_network_changes_fail_closed(self):
        begin = self.start().json()
        body = dict(test_id=begin['test_id'], wifi=self.sign(begin['wifi'],
                    self.c.evidence(bssid='c6:0b:cc:3b:1b:1e')), ble=self.sign(begin['ble'], self.evidence()))
        self.f.current += timedelta(seconds=8)
        response = self.finish(body)
        self.assertEqual(response.json()['reason_code'], 'WIFI_BSSID_MISMATCH')
        self.assertEqual(response.json()['test_result'], 'FAIL')
        begin, body = self.ready()
        outside = TestClient(self.f.app, client=('198.51.100.1', 12345))
        try:
            response = self.finish(body, client=outside,
                headers={**self.f.headers, 'X-Forwarded-For': '192.0.2.10'})
        finally:
            outside.close()
        self.assertEqual(response.json()['reason_code'], 'NETWORK_NOT_AUTHORIZED')
        self.assertEqual(response.json()['test_result'], 'FAIL')

    def test_replay_cross_test_and_signature_tampering_rejected(self):
        begin, body = self.ready()
        self.assertEqual(self.finish(body).json()['test_result'], 'PASS')
        self.assertEqual(self.finish(body).json()['code'], 'BLE_CHALLENGE_REPLAYED')
        second, another = self.ready()
        self.assertEqual(self.finish(another | {'wifi': body['wifi']}).json()['code'], 'TEST_BINDING_MISMATCH')
        evidence = self.evidence()
        another['ble'] = self.sign(second['ble'], evidence, ec.generate_private_key(ec.SECP256R1()))
        response = self.finish(another)
        self.assertEqual(response.json()['reason_code'], 'INVALID_DEVICE_SIGNATURE')

    def test_same_evidence_resigned_under_a_new_test_nonce_is_rejected(self):
        begin = self.start().json()
        evidence = self.evidence()
        body = dict(test_id=begin['test_id'], wifi=self.sign(begin['wifi'], self.c.evidence()),
                    ble=self.sign(begin['ble'], evidence))
        self.f.current += timedelta(seconds=8)
        self.assertEqual(self.finish(body).json()['test_result'], 'PASS')
        begin = self.start().json()
        body = dict(test_id=begin['test_id'], wifi=self.sign(begin['wifi'], self.c.evidence()),
                    ble=self.sign(begin['ble'], evidence))
        self.f.current += timedelta(seconds=8)
        self.assertEqual(self.finish(body).json()['reason_code'], 'BLE_EVIDENCE_REPLAYED')

    def test_admin_test_table_requires_login_and_redacts_payloads(self):
        begin, body = self.ready()
        self.assertEqual(self.finish(body).json()['test_result'], 'PASS')
        panel = create_panel(self.f.engine, username='operator', password_hash=self.c.password_hash,
            ready=lambda: {'classroom_wifi': True}, now=lambda: self.f.current,
            database_port=3306, simulation_only=False)
        origin = 'http://127.0.0.1:8003'
        with TestClient(panel, base_url=origin, client=('127.0.0.1', 3210), follow_redirects=False) as client:
            self.assertEqual(client.get('/ble').status_code, 303)
            page = client.get('/login')
            csrf = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
            self.assertEqual(client.post('/login', headers={'Origin': origin}, data=dict(
                csrf=csrf, username='operator', password='test-password')).status_code, 303)
            page = client.get('/ble')
            self.assertEqual(page.status_code, 200, page.text)
            self.assertIn('Temporary Network + BLE Tests', page.text)
            self.assertIn('TEST_PASS', page.text)
            self.assertIn('NETWORK_BLE_TEST_PASS', page.text)
            for private in (begin['test_id'], 'TEST001', 'signing_payload', 'auth_token_hash'):
                self.assertNotIn(private, page.text)

    def test_session_pin_classroom_and_device_validation(self):
        for fields, expected in [({'pin': '000000'}, 'TEST_PIN_INVALID'),
                ({'session_id': 999999}, 'TEST_SESSION_NOT_ELIGIBLE'),
                ({'public_key_fingerprint': '0' * 64}, 'DEVICE_KEY_NOT_REGISTERED')]:
            self.assertEqual(self.start(**fields).json()['code'], expected)
        begin, body = self.ready()
        with self.f.sessions.begin() as db:
            db.get(SessionClassroom, self.c.session_id).revision += 1
        self.assertEqual(self.finish(body).json()['reason_code'], 'TEST_CLASSROOM_CHANGED')

    def test_ble_skew_cap_staleness_and_expiry_preserved(self):
        for skew, wait, expected in [(1500, 8, 'NETWORK_BLE_TEST_PASS'),
                (2001, 8, 'BLE_EVIDENCE_FUTURE'), (-1, 8, 'BLE_EVIDENCE_STALE'),
                (0, 46, 'WIFI_CHALLENGE_EXPIRED')]:
            begin = self.start().json()
            evidence = self.evidence()
            evidence['scan_started_at_ms'] += skew
            evidence['scan_completed_at_ms'] += skew
            body = dict(test_id=begin['test_id'], wifi=self.sign(begin['wifi'], self.c.evidence()),
                        ble=self.sign(begin['ble'], evidence))
            self.f.current += timedelta(seconds=wait)
            response = self.finish(body)
            self.assertEqual(response.json()['reason_code'], expected, response.text)

    def test_wrong_student_login_and_disabled_cidr_cannot_produce_test_pass(self):
        begin, body = self.ready()
        for student in ('TEST001', 'TEST002'):
            login = self.f.client.post('/login', json={'student_id': student, 'password': 'test-password'}).json()
            self.assertEqual(self.finish(body, headers={'Authorization': 'Bearer '+login['access_token']}).json()['code'],
                             'TEST_BINDING_MISMATCH')
        with self.f.sessions.begin() as db:
            for policy in db.scalars(select(NetworkPolicy)):
                policy.enabled = False
        response = self.start()
        self.assertEqual(response.json()['reason_code'], 'NO_ENABLED_NETWORK_POLICY')
        self.assertEqual(response.json()['test_result'], 'FAIL')
