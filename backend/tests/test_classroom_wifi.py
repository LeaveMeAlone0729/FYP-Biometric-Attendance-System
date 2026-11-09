"""Real REST and P-256 signatures; synthetic identity and isolated persistence."""
import base64
import json
import sys
import unittest
import contextlib
import io
import tempfile
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select, func
from fastapi.testclient import TestClient
from models import Attendance
from modules.devices.models import RegisteredDevice
from modules.classroom_wifi.models import ClassroomBase, WifiChallenge, WifiEvent
from modules.classroom_wifi.migration import upgrade
from modules.classroom_wifi.router import router
from modules.classroom_wifi.policies import change, listing
from modules.classroom_wifi.service import ClassroomWifiService
from security import hash_password
import test_device_registration as registration

PATH = '/api/v1/classroom-wifi'


class ClassroomWifiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.password_hash = hash_password('test-password')

    def setUp(self):
        self.f = registration.DeviceRegistrationTests(); self.f.password_hash = self.password_hash
        if hasattr(self, 'engine_override'): self.f.make_engine = lambda: self.engine_override
        self.f.setUp()
        self.assertEqual(self.f.client.get(PATH+'/classrooms',headers=self.f.headers).status_code,404)
        self.f.app.include_router(router)
        upgrade(self.f.engine); upgrade(self.f.engine)
        self.assertEqual(self.f.confirm(self.f.begin().json()).status_code, 201)
        with self.f.sessions() as db:
            self.device = db.scalar(select(RegisteredDevice)); self.fingerprint = self.device.public_key_fingerprint
        self.policy('add', policy_id='home', classroom='A', access_point='d8:42:a1:9e:de:2f', network_name='Ultraman_yap_5Ghz')

    def tearDown(self): self.f.tearDown()

    def policy(self, action, **kw):
        with self.f.sessions.begin() as db:
            return change(db, action, now=self.f.now, actor='synthetic-operator', **kw)

    def begin(self, headers=None, **changes):
        return self.f.client.post(PATH + '/challenges', headers=headers or self.f.headers,
            json=dict(classroom_id='A', public_key_fingerprint=self.fingerprint, **changes))

    def evidence(self, **changes):
        ms = ClassroomWifiService(self.f.app.state.context).milliseconds(self.f.now)
        return dict(status='AVAILABLE', connection_type='WIFI', permission_status='PRECISE_GRANTED',
            wifi_enabled=True, wifi_connected=True, location_enabled=True, ssid='Ultraman_yap_5Ghz',
            bssid='d8:42:a1:9e:de:2f', rssi_dbm=-46, observed_at_ms=ms, **changes)

    def body(self, challenge, evidence=None, key=None):
        text = json.dumps(self.evidence() if evidence is None else evidence)
        signature = (key or self.f.key).sign(base64.b64decode(challenge['signing_payload']) + b'\n' + text.encode(), ec.ECDSA(hashes.SHA256()))
        return dict(challenge_id=challenge['challenge_id'], evidence_payload=base64.b64encode(text.encode()).decode(),
                    signature=base64.b64encode(signature).decode())

    def verify(self, evidence=None):
        return self.f.client.post(PATH + '/verifications', headers=self.f.headers,
                                  json=self.body(self.begin().json(), evidence))

    def assert_code(self, response, code):
        self.assertEqual(response.json().get('reason_code', response.json().get('code')), code, response.text)

    def test_multiple_access_points_optional_ssid_and_no_rssi_gate(self):
        self.assert_code(self.verify(), 'CLASSROOM_WIFI_APPROVED')
        self.policy('add', policy_id='hotspot', classroom='A', access_point='c6:0b:cc:3b:1b:1e')
        e=self.evidence();e.update(bssid='c6:0b:cc:3b:1b:1e',ssid='Any hotspot',rssi_dbm=-125)
        self.assert_code(self.verify(e), 'CLASSROOM_WIFI_APPROVED')
        self.assertEqual(self.f.count(Attendance), 0)

    def test_wrong_bssid_and_ssid(self):
        e=self.evidence();e['bssid']='c6:0b:cc:3b:1b:1e'
        self.assert_code(self.verify(e), 'WIFI_BSSID_MISMATCH')
        e=self.evidence();e['ssid']='wrong'
        self.assert_code(self.verify(e), 'WIFI_SSID_MISMATCH')

    def test_missing_permissions_and_location(self):
        for k,v in [('permission_status','DENIED'),('location_enabled',False)]:
            e=self.evidence();e[k]=v
            self.assert_code(self.verify(e),'WIFI_PERMISSION_REQUIRED')

    def test_unavailable_mobile_missing_and_malformed(self):
        for changes,code in [({'wifi_enabled':False},'WIFI_UNAVAILABLE'),
            ({'wifi_connected':False,'connection_type':'MOBILE_DATA'},'WIFI_UNAVAILABLE'),
            ({'bssid':None},'WIFI_EVIDENCE_MISSING'),({'bssid':'wrong'},'WIFI_EVIDENCE_MALFORMED')]:
            e=self.evidence();e.update(changes);self.assert_code(self.verify(e),code)

    def test_stale_future_and_prechallenge_evidence(self):
        for offset in (-16000,6000,-3000):
            e=self.evidence();e['observed_at_ms']+=offset
            self.assert_code(self.verify(e),'WIFI_EVIDENCE_STALE')

    def test_replay_challenge_and_observation_resigned_under_new_nonce(self):
        ch=self.begin().json();body=self.body(ch)
        for expected in ('CLASSROOM_WIFI_APPROVED','WIFI_CHALLENGE_REPLAYED'):
            self.assert_code(self.f.client.post(PATH+'/verifications',headers=self.f.headers,json=body),expected)
        self.assert_code(self.verify(),'WIFI_EVIDENCE_REPLAYED')

    def test_invalid_signature_consumes_challenge(self):
        ch=self.begin().json();body=self.body(ch,key=ec.generate_private_key(ec.SECP256R1()))
        self.assert_code(self.f.client.post(PATH+'/verifications',headers=self.f.headers,json=body),'INVALID_DEVICE_SIGNATURE')
        self.assert_code(self.f.client.post(PATH+'/verifications',headers=self.f.headers,json=self.body(ch)),'WIFI_CHALLENGE_REPLAYED')

    def test_evidence_tampering_rejected(self):
        ch=self.begin().json();body=self.body(ch);e=self.evidence();e['bssid']='c6:0b:cc:3b:1b:1e'
        body['evidence_payload']=base64.b64encode(json.dumps(e).encode()).decode()
        self.assert_code(self.f.client.post(PATH+'/verifications',headers=self.f.headers,json=body),'INVALID_DEVICE_SIGNATURE')

    def test_wrong_student_and_session_cannot_consume_owner_challenge(self):
        ch=self.begin().json();body=self.body(ch)
        for headers in (self.f.login('DEVICE002'),self.f.login('DEVICE001')):
            self.assert_code(self.f.client.post(PATH+'/verifications',headers=headers,json=body),'WIFI_CHALLENGE_NOT_FOUND')
        self.assert_code(self.f.client.post(PATH+'/verifications',headers=self.f.headers,json=body),'CLASSROOM_WIFI_APPROVED')

    def test_revoked_device_unknown_fingerprint_and_expiry(self):
        response=self.f.client.post(PATH+'/challenges',headers=self.f.headers,json={'classroom_id':'A','public_key_fingerprint':'0'*64})
        self.assert_code(response,'DEVICE_KEY_NOT_REGISTERED')
        ch=self.begin().json();self.f.now+=timedelta(seconds=46)
        self.assert_code(self.f.client.post(PATH+'/verifications',headers=self.f.headers,json=self.body(ch)),'WIFI_CHALLENGE_EXPIRED')
        with self.f.sessions.begin() as db:db.get(RegisteredDevice,self.device.device_id).status='REVOKED'
        self.assert_code(self.begin(),'DEVICE_NOT_ACTIVE')

    def test_disable_retire_and_current_policy_rechecked_after_challenge(self):
        ch=self.begin().json();self.policy('disable',policy_id='home')
        self.assert_code(self.f.client.post(PATH+'/verifications',headers=self.f.headers,json=self.body(ch)),'NO_ENABLED_CLASSROOM_POLICY')
        self.policy('enable',policy_id='home');self.policy('retire',policy_id='home')
        with self.f.sessions() as db:
            self.assertEqual(listing(db),[]);self.assertTrue(listing(db,include_all=True)[0]['retired'])
        with self.assertRaises(ValueError):self.policy('enable',policy_id='home')

    def test_authentication_fields_and_classroom_listing(self):
        self.assertEqual(self.f.client.get(PATH+'/classrooms').status_code,401)
        self.assertEqual(self.f.client.get(PATH+'/classrooms',headers=self.f.headers).json()['classrooms'][0]['classroom_id'],'A')
        body=self.body(self.begin().json());body['PASS']=True
        self.assertEqual(self.f.client.post(PATH+'/verifications',headers=self.f.headers,json=body).status_code,422)

    def test_malformed_signed_json_and_audit(self):
        ch=self.begin().json();body=self.body(ch);body['evidence_payload']=base64.b64encode(b'{"status":1,"status":2}').decode()
        self.assert_code(self.f.client.post(PATH+'/verifications',headers=self.f.headers,json=body),'WIFI_EVIDENCE_MALFORMED')
        with self.f.sessions() as db:
            self.assertEqual(db.scalar(select(WifiEvent).where(WifiEvent.result=='FAIL')).reason_code,'WIFI_EVIDENCE_MALFORMED')

    def test_concurrent_submissions_one_success_mariadb(self):
        if self.f.engine.dialect.name!='mysql':self.skipTest('Real row-lock test runs in isolated MariaDB suite')
        body=self.body(self.begin().json())
        def run(_):
            with TestClient(self.f.app) as client:return client.post(PATH+'/verifications',headers=self.f.headers,json=body).json()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
        self.assertEqual(sum(r.get('result')=='PASS' for r in results),1)
        self.assertEqual(sum(r.get('code')=='WIFI_CHALLENGE_REPLAYED' for r in results),1)

    def test_migration_keeps_core_metadata_optional_and_data(self):
        from models import Base
        self.assertFalse(set(ClassroomBase.metadata.tables)&set(Base.metadata.tables))
        core_tables=set(Base.metadata.tables)
        self.assertEqual(set(upgrade(self.f.engine)),set(ClassroomBase.metadata.tables))
        self.assertEqual(set(Base.metadata.tables),core_tables)
        self.assertEqual(self.f.count(RegisteredDevice),1)

    def test_operator_cli_add_list_enable_disable_retire_and_invalid_values(self):
        from fyp_test import main
        with tempfile.TemporaryDirectory(prefix='manual-android-') as folder, \
                patch('fyp_test.load_profile',return_value={}), \
                patch('fyp_test.install_network_guard'), \
                patch('fyp_test.operator_engine',return_value=self.f.engine), \
                patch.object(self.f.engine,'dispose'):
            # Policy timestamps use the real configured timezone; no target defaults.
            with patch('fyp_test.load_profile',return_value={'timezone':'Asia/Kuala_Lumpur'}):
                def run(*args):
                    output=io.StringIO()
                    with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
                        code=main(['--environment',folder,'classroom',*args])
                    return code,output.getvalue()
                self.assertEqual(run('add','--id','second','--classroom','A','--bssid','c6:0b:cc:3b:1b:1e','--simulation')[0],0)
                self.assertEqual(len(json.loads(run('list')[1])['policies']),2)
                for command in ('disable','enable','retire'):
                    self.assertEqual(run(command,'--id','second')[0],0)
                self.assertEqual(len(json.loads(run('list')[1])['policies']),1)
                self.assertNotEqual(run('enable','--id','second')[0],0)
                self.assertNotEqual(run('add','--id','bad','--classroom','A','--bssid','not-mac','--simulation')[0],0)

    def test_two_active_slots_can_independently_submit_signed_observations(self):
        from modules.devices.crypto import canonical_public_key
        key=ec.generate_private_key(ec.SECP256R1())
        body=self.f.body(key);public,fingerprint=canonical_public_key(body['public_key_spki'])
        with self.f.sessions.begin() as db:
            db.add(RegisteredDevice(device_id='synthetic-slot-two',student_id='DEVICE001',slot_number=2,
                public_key_spki=public,public_key_fingerprint=fingerprint,device_name='Synthetic tablet',
                device_model='Synthetic',platform='android',status='ACTIVE',registered_at=self.f.now))
        self.assert_code(self.verify(),'CLASSROOM_WIFI_APPROVED')
        ch=self.f.client.post(PATH+'/challenges',headers=self.f.headers,json={
            'classroom_id':'A','public_key_fingerprint':fingerprint}).json()
        result=self.f.client.post(PATH+'/verifications',headers=self.f.headers,json=self.body(ch,key=key))
        self.assert_code(result,'CLASSROOM_WIFI_APPROVED')
        self.assertEqual(result.json()['device_id'],'synthetic-slot-two')
