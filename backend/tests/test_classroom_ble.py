"""Actual REST/P-256; synthetic BLE observations, no hardware/attendance claims."""
import base64,json,sys,unittest,tempfile,contextlib,io
from pathlib import Path
from dataclasses import replace
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from models import Attendance, AuthSession
from modules.devices.models import RegisteredDevice
from modules.classroom_wifi.migration import upgrade as wifi_upgrade
from modules.classroom_ble.migration import upgrade
from modules.classroom_ble.models import BlePolicy,BleChallenge,BleEvent
from modules.classroom_ble.policies import change,listing
from modules.classroom_ble.service import BleVerificationService
from modules.classroom_ble.router import router
from security import digest, hash_password
import test_device_registration as registration

UUID='7d9a6c10-326a-4c60-9e01-1ef000000001'
OTHER='7d9a6c10-326a-4c60-9e01-1ef000000002'
PATH='/api/v1/classroom-ble'

class ClassroomBleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.password_hash=hash_password('test-password')
    def setUp(self):
        self.f=registration.DeviceRegistrationTests();self.f.password_hash=self.password_hash
        if hasattr(self,'engine_override'):self.f.make_engine=lambda:self.engine_override
        self.f.setUp();self.assertEqual(self.f.client.get(PATH+'/classrooms',headers=self.f.headers).status_code,404)
        wifi_upgrade(self.f.engine);upgrade(self.f.engine);upgrade(self.f.engine)
        self.f.app.include_router(router)
        self.assertEqual(self.f.confirm(self.f.begin().json()).status_code,201)
        with self.f.sessions() as db:self.device=db.scalar(select(RegisteredDevice));self.fingerprint=self.device.public_key_fingerprint
        self.policy('add',policy_id='test-beacon',classroom='A',service_uuid=UUID)
        self.policy('enable',policy_id='test-beacon')
    def tearDown(self):self.f.tearDown()
    def policy(self,action,**kw):
        with self.f.sessions.begin() as db:return change(db,action,now=self.f.now,actor='synthetic-operator',**kw)
    def begin(self,headers=None,classroom='A',fingerprint=None):
        return self.f.client.post(PATH+'/challenges',headers=headers or self.f.headers,json=dict(classroom_id=classroom,public_key_fingerprint=fingerprint or self.fingerprint))
    def evidence(self,samples=5,rssi=-55,uuid=UUID):
        start=BleVerificationService(self.f.app.state.context).ms(self.f.now)
        return dict(scan_status='COMPLETE',bluetooth_enabled=True,scan_permission='GRANTED',connect_permission='GRANTED',
            location_permission='PRECISE_GRANTED',location_enabled=True,scan_started_at_ms=start,scan_completed_at_ms=start+8000,
            scan_duration_ms=8000,beacons=[dict(service_uuid=uuid,samples=[dict(offset_us=100000+i*1000000,rssi_dbm=rssi) for i in range(samples)])])
    def body(self,ch,e,key=None):
        text=json.dumps(e,separators=(',',':')).encode();sig=(key or self.f.key).sign(base64.b64decode(ch['signing_payload'])+b'\n'+text,ec.ECDSA(hashes.SHA256()))
        return dict(challenge_id=ch['challenge_id'],evidence_payload=base64.b64encode(text).decode(),signature=base64.b64encode(sig).decode())
    def send(self,body,headers=None):
        response=self.f.client.post(PATH+'/verifications',headers=headers or self.f.headers,json=body)
        self.assertEqual(self.f.count(Attendance),0)
        return response
    def verify(self,e=None,key=None):
        ch=self.begin().json();body=self.body(ch,e or self.evidence(),key)
        self.f.now+=timedelta(seconds=8)
        return self.send(body)
    def code(self,response,expected):self.assertEqual(response.json().get('reason_code',response.json().get('code')),expected,response.text)

    def test_valid_beacon_pass_median_recomputed_no_attendance(self):
        e=self.evidence();e['beacons'][0]['samples'][0]['rssi_dbm']=-100
        r=self.verify(e);self.code(r,'BLE_APPROVED');self.assertEqual(r.json()['median_rssi_dbm'],-55)
        self.assertEqual(r.json()['observation_status'],'DETECTED')
        self.assertEqual(r.json()['observed_service_uuid'],UUID)
        self.assertEqual(r.json()['scan_duration_ms'],8000)
        self.assertFalse(r.json()['attendance_authorized']);self.assertEqual(self.f.count(Attendance),0)
        with self.f.sessions() as db:self.assertEqual(db.get(BleEvent,r.json()['verification_id']).sample_count,5)
    def test_policy_disabled_by_default_enable_disable_remove_preserves_audit(self):
        self.policy('add',policy_id='new',classroom='B',service_uuid=OTHER)
        self.code(self.begin(classroom='B'),'NO_ENABLED_BLE_POLICY')
        with self.f.sessions() as db:self.assertFalse(db.get(BlePolicy,'new').enabled)
        self.policy('enable',policy_id='new');self.assertEqual(self.begin(classroom='B').status_code,201)
        self.policy('disable',policy_id='new');self.code(self.begin(classroom='B'),'NO_ENABLED_BLE_POLICY')
        self.policy('remove',policy_id='new')
        with self.f.sessions() as db:self.assertTrue(any(p['retired'] for p in listing(db,include_all=True)))
        with self.assertRaises(ValueError):self.policy('enable',policy_id='new')
    def test_wrong_uuid_and_beacon_missing_fail(self):
        for missing in (False, True):
            evidence=self.evidence(uuid=OTHER)
            if missing:evidence['beacons']=[]
            r=self.verify(evidence)
            self.code(r,'BLE_BEACON_NOT_FOUND')
            self.assertEqual(r.json()['observation_status'],'NOT_DETECTED')
            self.assertIsNone(r.json()['observed_service_uuid'])
    def test_samples_insufficient_uncertain_weak_fail(self):
        r=self.verify(self.evidence(samples=2));self.code(r,'BLE_INSUFFICIENT_SAMPLES');self.assertEqual(r.json()['result'],'UNCERTAIN')
        r=self.verify(self.evidence(rssi=-101));self.code(r,'BLE_SIGNAL_WEAK')
        self.assertEqual(r.json()['observation_status'],'DETECTED')
        self.assertEqual(r.json()['observed_service_uuid'],UUID)
    def test_duplicate_copies_of_one_sample_rejected_but_equal_rssi_allowed(self):
        e=self.evidence();e['beacons'][0]['samples']=[e['beacons'][0]['samples'][0]]*5
        self.code(self.verify(e),'BLE_DUPLICATE_OBSERVATION')
        self.code(self.verify(),'BLE_APPROVED')
    def test_stale_and_future_timestamps_rejected(self):
        e=self.evidence();e['scan_started_at_ms']-=20000;e['scan_completed_at_ms']-=20000
        r=self.verify(e);self.code(r,'BLE_EVIDENCE_STALE')
        self.assertEqual(r.json()['observation_status'],'UNAVAILABLE')
        e=self.evidence();e['scan_started_at_ms']+=20000;e['scan_completed_at_ms']+=20000
        self.code(self.verify(e),'BLE_EVIDENCE_FUTURE')
    def test_signed_scan_wall_clock_boundaries_and_timezone_offset(self):
        context = self.f.app.state.context
        context.settings = replace(context.settings, timezone='Asia/Kuala_Lumpur')
        # The fixture server clock reads 12:00 MYT. Build the client epoch
        # independently so a shared conversion bug cannot make this test pass.
        utc = datetime.fromisoformat('2026-10-30T04:00:00+00:00')
        offset = datetime.fromisoformat('2026-10-30T09:30:00+05:30')
        self.assertEqual(utc, offset)
        issued_ms = int(utc.timestamp() * 1000)
        cases = (
            (0, 'BLE_APPROVED'),
            (1500, 'BLE_APPROVED'),
            (2000, 'BLE_APPROVED'),
            (2001, 'BLE_EVIDENCE_FUTURE'),
            (-1, 'BLE_EVIDENCE_STALE'),
        )
        for index, (skew_ms, expected) in enumerate(cases):
            with self.subTest(skew_ms=skew_ms):
                challenge = self.begin().json()
                payload = json.loads(base64.b64decode(challenge['signing_payload']))
                self.assertEqual(payload['issued_at_ms'], issued_ms + index * 8000)
                start = int((offset + timedelta(seconds=index * 8)).timestamp() * 1000) + skew_ms
                evidence = self.evidence()
                evidence.update(scan_started_at_ms=start, scan_completed_at_ms=start + 8000)
                self.f.now += timedelta(seconds=8)
                response = self.send(self.body(challenge, evidence))
                self.code(response, expected)
                self.assertFalse(response.json()['attendance_authorized'])
        self.assertEqual(self.f.count(Attendance), 0)
    def test_captured_scan_completion_skew_passes_signed_verification(self):
        # Offsets in milliseconds from the physical challenge's issue time.
        # The event timestamp follows validation and bounds it from above.
        for clock_delta in (1435, 0):
            with self.subTest(clock_delta=clock_delta):
                challenge = self.begin().json()
                issued = json.loads(base64.b64decode(challenge['signing_payload']))['issued_at_ms']
                evidence = self.evidence()
                evidence.update(
                    scan_started_at_ms=issued + 21 + clock_delta,
                    scan_completed_at_ms=issued + 8059 + clock_delta,
                    scan_duration_ms=8035,
                )
                self.f.now += timedelta(milliseconds=8160)
                response = self.send(self.body(challenge, evidence))
                self.code(response, 'BLE_APPROVED')
                self.assertFalse(response.json()['attendance_authorized'])
        self.assertEqual(self.f.count(Attendance), 0)

    def test_start_plus_duration_cannot_exceed_future_cap(self):
        evidence = self.evidence()
        evidence['scan_started_at_ms'] += 2001
        # Wall-clock completion alone is only 1,500 ms ahead.
        evidence['scan_completed_at_ms'] += 1500
        self.code(self.verify(evidence), 'BLE_EVIDENCE_FUTURE')

    def test_scan_must_fit_after_challenge_issuance(self):
        challenge = self.begin().json()
        evidence = self.evidence()
        evidence['scan_started_at_ms'] += 1500
        evidence['scan_completed_at_ms'] += 1500
        # Reported start is after issuance, but the scan cannot fit into
        # the 7,999 ms that the server has allowed to elapse.
        self.f.now += timedelta(milliseconds=7999)
        self.code(self.send(self.body(challenge, evidence)), 'BLE_EVIDENCE_STALE')

    def test_positive_skew_cannot_extend_scan_or_sample_age(self):
        cases = (
            (15_100, True, 'BLE_APPROVED'),
            (15_101, True, 'BLE_EVIDENCE_STALE'),
            (30_000, False, 'BLE_BEACON_NOT_FOUND'),
            (30_001, False, 'BLE_EVIDENCE_STALE'),
        )
        for elapsed_ms, beacon, expected in cases:
            with self.subTest(elapsed_ms=elapsed_ms, beacon=beacon):
                challenge = self.begin().json()
                evidence = self.evidence()
                evidence['scan_started_at_ms'] += 1500
                evidence['scan_completed_at_ms'] += 1500
                if not beacon:
                    evidence['beacons'] = []
                self.f.now += timedelta(milliseconds=elapsed_ms)
                self.code(self.send(self.body(challenge, evidence)), expected)

    def test_policy_age_checked_for_each_sample(self):
        ch=self.begin().json();body=self.body(ch,self.evidence());self.f.now+=timedelta(seconds=16)
        self.code(self.send(body),'BLE_EVIDENCE_STALE')
    def test_expired_challenge_and_replay_rejected(self):
        ch = self.begin().json()
        evidence = self.evidence()
        evidence['scan_started_at_ms'] += 38_500
        evidence['scan_completed_at_ms'] += 38_500
        body = self.body(ch, evidence)
        self.f.now += timedelta(seconds=45)
        self.code(self.send(body),'BLE_CHALLENGE_EXPIRED')
        ch=self.begin().json();body=self.body(ch,self.evidence());self.f.now+=timedelta(seconds=8)
        self.code(self.send(body),'BLE_APPROVED');self.code(self.send(body),'BLE_CHALLENGE_REPLAYED')

    def test_expired_session_rejects_scan_within_future_cap(self):
        expires = self.f.now + timedelta(seconds=8)
        token_hash = digest(self.f.headers['Authorization'].split()[1])
        with self.f.sessions.begin() as db:
            db.get(AuthSession, token_hash).expires_at = expires
        ch = self.begin().json()
        evidence = self.evidence()
        evidence['scan_started_at_ms'] += 1500
        evidence['scan_completed_at_ms'] += 1500
        self.f.now = expires
        self.assertEqual(self.send(self.body(ch, evidence)).status_code, 401)

    def test_same_report_resigned_under_another_preissued_nonce_rejected(self):
        a=self.begin().json();b=self.begin().json();e=self.evidence()
        e['scan_started_at_ms'] += 1500
        e['scan_completed_at_ms'] += 1500
        self.f.now+=timedelta(seconds=8)
        self.code(self.send(self.body(a,e)),'BLE_APPROVED');self.code(self.send(self.body(b,e)),'BLE_EVIDENCE_REPLAYED')
    def test_invalid_signature_consumes_challenge(self):
        ch=self.begin().json();e=self.evidence();self.f.now+=timedelta(seconds=8)
        self.code(self.send(self.body(ch,e,ec.generate_private_key(ec.SECP256R1()))),'INVALID_DEVICE_SIGNATURE')
        self.code(self.send(self.body(ch,e)),'BLE_CHALLENGE_REPLAYED')

    def test_modifying_signed_timestamps_inside_future_cap_is_rejected(self):
        challenge = self.begin().json()
        evidence = self.evidence()
        body = self.body(challenge, evidence)
        evidence['scan_started_at_ms'] += 1500
        evidence['scan_completed_at_ms'] += 1500
        body['evidence_payload'] = base64.b64encode(json.dumps(evidence).encode()).decode()
        self.f.now += timedelta(seconds=8)
        self.code(self.send(body), 'INVALID_DEVICE_SIGNATURE')
    def test_wrong_student_session_classroom_and_inactive_device(self):
        ch=self.begin().json();body=self.body(ch,self.evidence())
        for headers in (self.f.login('DEVICE002'),self.f.login('DEVICE001')):self.code(self.send(body,headers),'BLE_CHALLENGE_NOT_FOUND')
        self.code(self.begin(classroom='missing'),'NO_ENABLED_BLE_POLICY')
        self.policy('add',policy_id='other-room',classroom='B',service_uuid=OTHER);self.policy('enable',policy_id='other-room')
        other_ch=self.begin(classroom='B').json();other_body=self.body(other_ch,self.evidence())
        self.f.now+=timedelta(seconds=8);self.code(self.send(other_body),'BLE_BEACON_NOT_FOUND')
        self.code(self.begin(fingerprint='0'*64),'DEVICE_KEY_NOT_REGISTERED')
        with self.f.sessions.begin() as db:db.get(RegisteredDevice,self.device.device_id).status='REVOKED'
        self.code(self.begin(),'DEVICE_NOT_ACTIVE');self.code(self.send(body),'DEVICE_NOT_ACTIVE')
    def test_bluetooth_and_permissions_unavailable_are_uncertain(self):
        for changes,code in [({'bluetooth_enabled':False},'BLUETOOTH_OFF'),({'scan_permission':'DENIED'},'BLE_PERMISSION_REQUIRED'),
            ({'location_permission':'APPROXIMATE_ONLY'},'BLE_PERMISSION_REQUIRED'),({'location_enabled':False},'BLE_PERMISSION_REQUIRED'),
            ({'scan_status':'BLE_SCAN_FAILED'},'BLE_UNAVAILABLE'),({'scan_status':'STOPPED'},'BLE_SCAN_INCOMPLETE')]:
            e=self.evidence();e.update(changes);e['beacons']=[];r=self.verify(e);self.code(r,code);self.assertEqual(r.json()['result'],'UNCERTAIN')
            self.assertEqual(r.json()['observation_status'],'UNAVAILABLE')
    def test_duplicate_uuid_cannot_be_enabled_in_same_or_other_classroom(self):
        with self.assertRaisesRegex(ValueError,'BLE_UUID_INVALID'):
            self.policy('add',policy_id='invalid',classroom='A',service_uuid='invalid')
        for room in ('A','B'):
            policy_id=f'duplicate-{room}'
            self.policy('add',policy_id=policy_id,classroom=room,service_uuid=UUID.upper())
            with self.assertRaisesRegex(ValueError,'BLE_UUID_ALREADY_ENABLED'):
                self.policy('enable',policy_id=policy_id)
            with self.f.sessions() as db:self.assertFalse(db.get(BlePolicy,policy_id).enabled)
        self.policy('disable',policy_id='test-beacon')
        self.assertTrue(self.policy('enable',policy_id='duplicate-B')['enabled'])
    def test_multiple_approved_beacons_and_unrelated_ignored(self):
        self.policy('add',policy_id='second',classroom='A',service_uuid=OTHER);self.policy('enable',policy_id='second')
        self.code(self.verify(self.evidence(uuid=OTHER)),'BLE_APPROVED')
        e=self.evidence();e['beacons'].append(dict(service_uuid='7d9a6c10-326a-4c60-9e01-1ef000000099',samples=[dict(offset_us=1,rssi_dbm=0)]))
        r=self.verify(e);self.code(r,'BLE_APPROVED');self.assertEqual(r.json()['sample_count'],5)
    def test_disabled_or_changed_policy_after_issue_cannot_pass(self):
        ch=self.begin().json();e=self.evidence();self.policy('disable',policy_id='test-beacon');self.f.now+=timedelta(seconds=8)
        self.code(self.send(self.body(ch,e)),'NO_ENABLED_BLE_POLICY')
        self.policy('enable',policy_id='test-beacon');ch=self.begin().json();e=self.evidence()
        self.policy('disable',policy_id='test-beacon');self.policy('enable',policy_id='test-beacon');self.f.now+=timedelta(seconds=8)
        self.code(self.send(self.body(ch,e)),'BLE_POLICY_CHANGED')
    def test_malformed_rssi_sample_bound_duration_and_client_median(self):
        cases=[]
        e=self.evidence();e['median_rssi']=-1;cases.append(e)
        e=self.evidence();e['beacons'][0]['samples'][0]['rssi_dbm']=127;cases.append(e)
        e=self.evidence();e['beacons'][0]['samples'][0]['offset_us']=9000000;cases.append(e)
        e=self.evidence();e['scan_duration_ms']=12000;cases.append(e)
        for e in cases:self.code(self.verify(e),'BLE_EVIDENCE_MALFORMED')
        self.assertEqual(self.f.count(Attendance),0)
    def test_auth_classrooms_and_client_pass_rejected(self):
        self.assertEqual(self.f.client.get(PATH+'/classrooms').status_code,401)
        self.assertTrue(self.f.client.get(PATH+'/classrooms',headers=self.f.headers).json()['simulation_only'])
        body=self.body(self.begin().json(),self.evidence());body['PASS']=True
        self.assertEqual(self.send(body).status_code,422)
        self.assertEqual(self.f.client.post(PATH+'/challenges',headers=self.f.headers,json={'classroom_id':'A','public_key_fingerprint':self.fingerprint,'device_id':'forged-device'}).status_code,422)
    def test_operator_commands_are_implemented_and_disabled_by_default(self):
        from fyp_test import main
        with tempfile.TemporaryDirectory(prefix='manual-android-') as folder,patch('fyp_test.load_profile',return_value={'timezone':'Asia/Kuala_Lumpur'}),patch('fyp_test.install_network_guard'),patch('fyp_test.operator_engine',return_value=self.f.engine),patch.object(self.f.engine,'dispose'):
            def run(*args):
                out=io.StringIO()
                with contextlib.redirect_stdout(out),contextlib.redirect_stderr(out):code=main(['--environment',folder,'ble',*args])
                return code,out.getvalue()
            self.assertEqual(run('add','--id','cli','--classroom','A','--uuid',OTHER,'--simulation')[0],0)
            self.assertFalse(json.loads(run('list')[1])['policies'][0]['enabled'])
            for command in ('enable','disable','remove'):self.assertEqual(run(command,'--id','cli')[0],0)
            self.assertNotEqual(run('enable','--id','cli')[0],0)
    def test_concurrent_confirmations_consume_once_mariadb(self):
        if self.f.engine.dialect.name!='mysql':self.skipTest('Real MariaDB row locks')
        ch=self.begin().json();body=self.body(ch,self.evidence());self.f.now+=timedelta(seconds=8)
        def run(_):
            with TestClient(self.f.app) as client:return client.post(PATH+'/verifications',headers=self.f.headers,json=body).json()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
        self.assertEqual(sum(r.get('result')=='PASS' for r in results),1);self.assertEqual(sum(r.get('code')=='BLE_CHALLENGE_REPLAYED' for r in results),1)
