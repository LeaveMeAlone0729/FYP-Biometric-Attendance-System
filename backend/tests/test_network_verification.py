"""FR-06 real REST/persistence with controlled ASGI peers; no production policies."""
import base64,json,os,re,secrets,socket,sys,threading,time,unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from sqlalchemy import select,func,text
from sqlalchemy.exc import IntegrityError
from config import Settings
from database import make_engine
from models import Student,AuthSession,Attendance
from security import digest,hash_password
from modules.networks.cidr import canonical_cidr
from modules.networks.models import NetworkPolicy,NetworkPolicyEvent,NetworkVerificationEvent,NETWORK_TABLES
from modules.networks.policies import put_policy
from modules.networks.service import NetworkVerificationService
from modules.networks.migration import upgrade_network_schema
import test_device_registration as registration

PATH='/api/v1/networks/verifications'

class NetworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.password_hash=hash_password('test-password')
    def setUp(self):
        self.f=registration.DeviceRegistrationTests();self.f.password_hash=self.password_hash
        if hasattr(self,'engine_override'):self.f.make_engine=lambda:self.engine_override
        self.f.setUp()
    def tearDown(self):self.f.tearDown()
    def policy(self,identifier='sim-v4',cidr='192.0.2.0/24',enabled=True):
        with self.f.sessions.begin() as db:return put_policy(db,network_id=identifier,name='Controlled simulation',cidr=cidr,enabled=enabled,actor='isolated-test-operator',now=self.f.now)
    def request(self,source='192.0.2.10',headers=None,body=None):
        client=TestClient(self.f.app,client=(source,32123))
        try:return client.post(PATH,headers={**self.f.headers,**(headers or {})},json={} if body is None else body)
        finally:client.close()
    def count(self,model):
        with self.f.sessions() as db:return db.scalar(select(func.count()).select_from(model))
    def scope(self,scope,**kwargs):
        with self.f.sessions.begin() as db:
            student=db.get(Student,'DEVICE001');auth=db.get(AuthSession,digest(self.f.headers['Authorization'].split()[1]))
            return NetworkVerificationService(self.f.app.state.context).verify(db,student,auth,scope,**kwargs)
    def test_authorized_pass_has_server_policy_audit_and_zero_attendance(self):
        self.policy();response=self.request();self.assertEqual(response.status_code,200,response.text)
        result=response.json();self.assertEqual(result['result'],'PASS');self.assertEqual(result['matched_policy_id'],'sim-v4')
        self.assertEqual(result['source_ip'],'192.0.2.10');self.assertFalse(result['attendance_authorized'])
        with self.f.sessions() as db:
            event=db.get(NetworkVerificationEvent,result['verification_id']);self.assertEqual(event.student_id,'DEVICE001')
            self.assertEqual(event.result,'PASS');self.assertEqual(event.policy_cidr,'192.0.2.0/24');self.assertEqual(event.verified_at,self.f.now)
            self.assertNotEqual(event.auth_token_hash,self.f.headers['Authorization'].split()[1])
        self.assertEqual(self.count(Attendance),0)
    def test_login_profile_available_without_authorized_attendance_network(self):
        # Login/profile need valid credentials, not an attendance CIDR verdict.
        client=TestClient(self.f.app,client=('198.51.100.9',32123))
        try:
            login=client.post('/login',json={'student_id':'DEVICE001','password':'test-password'})
            self.assertEqual(login.status_code,200)
            headers={'Authorization':'Bearer '+login.json()['access_token']}
            for configured in ('absent','disabled','outside'):
                if configured=='disabled':self.policy(enabled=False)
                elif configured=='outside':self.policy(enabled=True)
                self.assertEqual(client.get('/me',headers=headers).status_code,200)
                result=client.post(PATH,headers=headers,json={}).json()
                self.assertEqual(result['result'],'FAIL')
                self.assertFalse(result['attendance_authorized'])
            self.assertEqual(self.count(Attendance),0)
        finally:client.close()
    def test_fake_wifi_claims_never_authorize_network(self):
        self.policy()
        for field in ('ssid','bssid','wifi_name','campus_wifi','is_authorized_wifi'):
            self.assertEqual(self.request('198.51.100.9',body={field:'claimed-campus'}).status_code,422)
        result=self.request('198.51.100.9',headers={'X-Wifi-SSID':'claimed-campus','X-Network-Verified':'PASS'}).json()
        self.assertEqual(result['result'],'FAIL')
        self.assertEqual(result['source_ip'],'198.51.100.9')
        self.assertEqual(self.count(Attendance),0)
    def test_outside_network_and_missing_or_disabled_policy_fail(self):
        self.assertEqual(self.request().json()['reason_code'],'NO_ENABLED_NETWORK_POLICY')
        self.policy(enabled=False);self.assertEqual(self.request().json()['result'],'FAIL')
        self.policy();response=self.request('198.51.100.8').json()
        self.assertEqual(response['reason_code'],'NETWORK_NOT_AUTHORIZED');self.assertIsNone(response['matched_policy_id'])
        self.assertEqual(self.count(NetworkVerificationEvent),3);self.assertEqual(self.count(Attendance),0)
    def test_invalid_enabled_policy_blocks_even_another_matching_policy(self):
        self.policy();self.policy('damaged','203.0.113.0/24')
        with self.f.sessions.begin() as db:db.execute(text("UPDATE network_policies SET network_cidr='invalid-policy' WHERE network_id='damaged'"))
        result=self.request().json();self.assertEqual(result['result'],'FAIL');self.assertEqual(result['reason_code'],'NETWORK_POLICY_INVALID')
        with self.f.sessions.begin() as db:db.execute(text("UPDATE network_policies SET enabled=0 WHERE network_id='damaged'"))
        self.assertEqual(self.request().json()['result'],'PASS')
    def test_policy_input_validation_and_configuration_audit(self):
        for value in ['bad','192.0.2.1/24','192.0.2.1','192.0.2.0/33','2001:db8::1/64','fe80::%eth0/64','::ffff:192.0.2.0/120']:
            with self.assertRaises(ValueError):self.policy(cidr=value)
        self.assertEqual(self.count(NetworkPolicy),0)
        self.assertEqual(canonical_cidr('2001:0db8:0000::/48'),'2001:db8::/48')
        self.policy();self.policy(enabled=False)
        self.assertEqual(self.count(NetworkPolicyEvent),2)
        with self.f.sessions() as db:
            events=db.scalars(select(NetworkPolicyEvent).order_by(NetworkPolicyEvent.event_id)).all()
            self.assertIsNone(events[0].previous_value);self.assertEqual(json.loads(events[1].previous_value)['enabled'],True)
    def test_forwarded_headers_ignored_and_client_ip_fields_rejected(self):
        self.policy()
        for header in [{'X-Forwarded-For':'192.0.2.10'},{'Forwarded':'for=192.0.2.10'},{'X-Real-IP':'192.0.2.10'},{'X-Forwarded-For':'192.0.2.10, 127.0.0.1'}]:
            result=self.request('198.51.100.9',header).json();self.assertEqual(result['result'],'FAIL');self.assertEqual(result['source_ip'],'198.51.100.9')
        for key in ['source_ip','ip','network_verified','result','operation','attendance_attempt_id']:
            self.assertEqual(self.request(body={key:'192.0.2.10'}).status_code,422)
        self.assertEqual(self.count(NetworkVerificationEvent),4)
    def test_authorized_asgi_peers_and_forged_vendor_header(self):
        # Retained core security case extracted from the removed isolated browser tests.
        self.policy()
        self.assertEqual(self.request('192.0.2.10').json()['result'],'PASS')
        self.assertEqual(self.request('198.51.100.8',{'CF-Connecting-IP':'192.0.2.10'}).json()['result'],'FAIL')
        self.assertEqual(self.request('127.0.0.1',{'CF-Connecting-IP':'192.0.2.10'}).json()['reason_code'],'LOOPBACK_SOURCE_NOT_AUTHORIZED')
        self.assertEqual(self.count(Attendance),0)
    def test_ipv6_ipv4_mapping_and_longest_prefix_selection(self):
        self.policy();self.policy('sim-v6','2001:db8:1234::/48')
        self.policy('specific','192.0.2.0/28')
        self.assertEqual(self.request('192.0.2.10').json()['matched_policy_id'],'specific')
        result=self.request('2001:db8:1234::8').json();self.assertEqual(result['result'],'PASS');self.assertEqual(result['matched_policy_id'],'sim-v6')
        self.assertEqual(self.request('2001:db8:9999::8').json()['result'],'FAIL')
        mapped=self.request('::ffff:192.0.2.10').json();self.assertEqual(mapped['source_ip'],'192.0.2.10');self.assertEqual(mapped['result'],'PASS')
    def test_loopback_never_silently_authorized_even_by_a_policy(self):
        self.policy(cidr='0.0.0.0/0');self.policy('v6-all','::/0')
        for source in ['127.0.0.1','127.0.0.2','::1','::ffff:127.0.0.1']:
            result=self.request(source).json();self.assertEqual(result['result'],'FAIL');self.assertEqual(result['reason_code'],'LOOPBACK_SOURCE_NOT_AUTHORIZED')
    def test_missing_invalid_unspecified_and_multicast_source_fail_and_audit(self):
        for scope,reason in [({},'SOURCE_IP_MISSING'),({'client':('bad',10)},'SOURCE_IP_INVALID'),({'client':('2001:db8::1%scope',10)},'SOURCE_IP_INVALID'),({'client':('0.0.0.0',10)},'SOURCE_IP_NOT_UNICAST'),({'client':('ff02::1',10)},'SOURCE_IP_NOT_UNICAST')]:
            result=self.scope(scope);self.assertEqual(result['result'],'FAIL');self.assertEqual(result['reason_code'],reason)
        self.assertEqual(self.count(NetworkVerificationEvent),5)
    def test_fresh_check_after_disabling_policy_never_reuses_pass(self):
        self.policy();first=self.request().json();self.policy(enabled=False);second=self.request().json()
        self.assertEqual(first['result'],'PASS');self.assertEqual(second['result'],'FAIL');self.assertNotEqual(first['verification_id'],second['verification_id'])
        with self.f.sessions() as db:self.assertEqual(db.get(NetworkVerificationEvent,first['verification_id']).policy_cidr,'192.0.2.0/24')
    def test_no_policy_write_api_and_authentication_required(self):
        self.assertEqual(self.f.client.post(PATH,json={}).status_code,401)
        self.assertEqual(self.f.client.post('/api/v1/networks/policies',headers=self.f.headers,json={}).status_code,404)
        self.f.now+=timedelta(hours=9);self.assertEqual(self.request().status_code,401)
        self.assertEqual(self.count(NetworkVerificationEvent),0)
    def test_later_attendance_interface_requires_server_owned_attempt(self):
        self.policy()
        with self.assertRaises(ValueError):self.scope({'client':('192.0.2.10',99)},operation='attendance_authorization')
        result=self.scope({'client':('192.0.2.10',99)},operation='attendance_authorization',attendance_attempt_id='isolated-server-attempt')
        self.assertEqual(result['result'],'PASS');self.assertFalse(result['attendance_authorized'])
        with self.f.sessions() as db:self.assertEqual(db.get(NetworkVerificationEvent,result['verification_id']).attendance_attempt_id,'isolated-server-attempt')
        self.assertEqual(self.count(Attendance),0)
    def test_actual_socket_ignores_spoofed_forwarded_header(self):
        import httpx,uvicorn
        self.policy();sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        self.assertNotEqual(port,8000)
        server=uvicorn.Server(uvicorn.Config(self.f.app,host='127.0.0.1',port=port,proxy_headers=False,access_log=False,log_level='error'))
        thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
        try:
            deadline=time.monotonic()+10
            while not server.started:
                if time.monotonic()>deadline:raise RuntimeError('Isolated server did not start')
                time.sleep(.05)
            response=httpx.post('http://127.0.0.1:'+str(port)+PATH,headers={**self.f.headers,'X-Forwarded-For':'192.0.2.10'},json={})
            self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['source_ip'],'127.0.0.1')
            self.assertEqual(response.json()['reason_code'],'LOOPBACK_SOURCE_NOT_AUTHORIZED')
        finally:server.should_exit=True;thread.join(timeout=10);sock.close()

@unittest.skipUnless(os.getenv('ATTENDANCE_DEVICE_MYSQL_TESTS')=='1','Opt-in isolated MariaDB FR-06 migration and concurrency')
class NetworkMariaDBTests(unittest.TestCase):
    def test_additive_migration_constraints_and_parallel_audits(self):
        import mysql.connector
        settings=Settings();schema='attendance_network_test_'+secrets.token_hex(6)
        control=mysql.connector.connect(host=settings.db_host,port=settings.db_port,user=settings.db_user,password=settings.db_password)
        harness=NetworkTests();created=False
        try:
            with control.cursor() as c:c.execute('CREATE DATABASE `'+schema+'` CHARACTER SET utf8mb4')
            created=True;harness.engine_override=make_engine(replace(settings,db_name=schema));harness.password_hash=hash_password('test-password');harness.setUp()
            # The new attendance audit references network evidence. Drop empty
            # dependent fixture tables first, only inside this disposable schema.
            from modules.authorization.models import AUTHORIZATION_TABLES
            for table in reversed(AUTHORIZATION_TABLES):table.drop(harness.engine_override)
            for table in reversed(NETWORK_TABLES):table.drop(harness.engine_override)
            report=upgrade_network_schema(harness.engine_override);self.assertEqual(len(report['created_tables']),3)
            self.assertEqual(upgrade_network_schema(harness.engine_override)['created_tables'],[])
            for table in AUTHORIZATION_TABLES:table.create(harness.engine_override)
            harness.policy()
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(harness.request,['192.0.2.2','198.51.100.2']))
            self.assertEqual(sorted(r.json()['result'] for r in results),['FAIL','PASS'])
            self.assertEqual(harness.count(NetworkVerificationEvent),2);self.assertEqual(harness.count(Attendance),0)
        finally:
            if hasattr(harness,'f'):harness.tearDown()
            if created:
                assert re.fullmatch('attendance_network_test_[0-9a-f]{12}',schema) and schema!=settings.db_name
                with control.cursor() as c:c.execute('DROP DATABASE `'+schema+'`')
            control.close()
