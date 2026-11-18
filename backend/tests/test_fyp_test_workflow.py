"""Disposable operator policy workflow + actual REST authorization boundaries."""
import contextlib
import io
import json
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from security import hash_password
from fyp_test import change_policy,policy_state,main,ManualTestGuardError
from modules.networks.models import NetworkPolicyEvent
import test_network_verification as network


class SimpleNetworkWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.password_hash=hash_password('test-password')

    def setUp(self):
        self.n=network.NetworkTests();self.n.password_hash=self.password_hash
        if hasattr(self,'engine_override'):self.n.engine_override=self.engine_override
        self.n.setUp()

    def tearDown(self):self.n.tearDown()

    def apply(self,command,**kw):
        with self.n.f.sessions.begin() as db:
            return change_policy(db,command,now=self.n.f.now,actor='synthetic-operator',**kw)

    def test_login_profile_independent_for_two_devices_with_different_network_results(self):
        self.apply('set',cidr='192.0.2.0/25')
        for source,result in [('192.0.2.10','PASS'),('192.0.2.200','FAIL')]:
            client=TestClient(self.n.f.app,client=(source,1234))
            try:
                response=client.post('/login',json={'student_id':'DEVICE001','password':'test-password'})
                self.assertEqual(response.status_code,200,response.text)
                headers={'Authorization':'Bearer '+response.json()['access_token']}
                self.assertEqual(client.get('/me',headers=headers).status_code,200)
                self.assertEqual(client.post(network.PATH,headers=headers,json={}).json()['result'],result)
            finally:client.close()
        self.assertEqual(self.n.count(network.Attendance),0)

    def test_policy_change_enable_disable_and_committed_state(self):
        self.apply('set',cidr='192.0.2.0/24')
        self.assertEqual(self.n.request().json()['result'],'PASS')
        self.apply('disable')
        self.assertEqual(self.n.request().json()['reason_code'],'NO_ENABLED_NETWORK_POLICY')
        self.apply('enable');self.apply('set',cidr='198.51.100.0/24')
        self.assertEqual(self.n.request().json()['result'],'FAIL')
        self.assertEqual(self.n.request('198.51.100.7').json()['result'],'PASS')
        with self.n.f.sessions() as db:
            self.assertEqual(policy_state(db)['cidr'],'198.51.100.0/24')
            self.assertEqual(db.scalar(select(func.count()).select_from(NetworkPolicyEvent)),4)

    def test_export_restore_preserves_audits_and_other_policy_rows(self):
        self.apply('set',cidr='192.0.2.0/24')
        with self.n.f.sessions() as db:snapshot={'format':'fyp-network-simulation-v1','policy':policy_state(db)}
        self.n.policy('unrelated-policy','203.0.113.0/24',False)
        self.apply('set',cidr='198.51.100.0/24');self.apply('restore',snapshot=snapshot)
        self.assertEqual(self.n.request().json()['result'],'PASS')
        self.apply('restore',snapshot={'format':'fyp-network-simulation-v1','policy':None})
        self.assertEqual(self.n.request().json()['reason_code'],'NO_ENABLED_NETWORK_POLICY')
        with self.n.f.sessions() as db:
            self.assertIsNotNone(policy_state(db))  # No destructive delete of referenced policy.
            self.assertIsNotNone(db.get(network.NetworkPolicy,'unrelated-policy'))

    def test_bad_cidr_and_bad_restore_do_not_change_committed_policy(self):
        self.apply('set',cidr='192.0.2.0/24')
        for cidr in ('bad','192.0.2.99/24'):
            with self.assertRaises(ValueError):self.apply('set',cidr=cidr)
        with self.assertRaises(ManualTestGuardError):
            self.apply('restore',snapshot={'format':'fyp-network-simulation-v1','policy':{'network_id':'another-policy'}})
        self.assertEqual(self.n.request().json()['result'],'PASS')

    def test_loopback_and_spoofed_forwarding_never_gain_attendance_authorization(self):
        self.apply('set',cidr='192.0.2.0/24')
        self.assertEqual(self.n.request('127.0.0.1').json()['reason_code'],'LOOPBACK_SOURCE_NOT_AUTHORIZED')
        response=self.n.request('198.51.100.7',headers={'X-Forwarded-For':'192.0.2.10','CF-Connecting-IP':'192.0.2.10'})
        self.assertEqual(response.json()['result'],'FAIL')
        self.assertEqual(response.json()['source_ip'],'198.51.100.7')
        self.assertFalse(response.json()['attendance_authorized'])
        self.assertEqual(self.n.count(network.Attendance),0)

    def test_cli_requires_explicit_simulation_for_setting_a_policy(self):
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:
            main(['policy','set','--cidr','192.0.2.0/24'])
        self.assertEqual(error.exception.code,2)

    def test_two_simultaneous_cidrs_match_independently_and_outside_fails(self):
        self.apply('add',identifier='sim-a',cidr='192.0.2.0/24',name='Network A')
        self.apply('add',identifier='sim-b',cidr='198.51.100.0/24',name='Network B')
        for source,identifier in [('192.0.2.10','sim-a'),('198.51.100.7','sim-b')]:
            result=self.n.request(source).json()
            self.assertEqual(result['result'],'PASS');self.assertEqual(result['matched_policy_id'],identifier)
        self.assertEqual(self.n.request('203.0.113.9').json()['reason_code'],'NETWORK_NOT_AUTHORIZED')
        self.assertEqual(self.n.count(network.Attendance),0)

    def test_disable_one_id_does_not_disable_other_cidr(self):
        self.apply('add',identifier='sim-a',cidr='192.0.2.0/24')
        self.apply('add',identifier='sim-b',cidr='198.51.100.0/24')
        self.apply('disable',identifier='sim-a')
        self.assertEqual(self.n.request().json()['result'],'FAIL')
        self.assertEqual(self.n.request('198.51.100.7').json()['result'],'PASS')
        self.apply('enable',identifier='sim-a')
        self.assertEqual(self.n.request().json()['result'],'PASS')

    def test_remove_disables_and_retains_prior_verification_and_audit(self):
        self.apply('add',identifier='sim-a',cidr='192.0.2.0/24')
        event=self.n.request().json()['verification_id']
        self.apply('remove',identifier='sim-a')
        self.assertEqual(self.n.request().json()['reason_code'],'NO_ENABLED_NETWORK_POLICY')
        with self.n.f.sessions() as db:
            self.assertFalse(db.get(network.NetworkPolicy,'sim-a').enabled)
            self.assertEqual(db.get(network.NetworkVerificationEvent,event).matched_policy_id,'sim-a')
            latest=db.scalar(select(NetworkPolicyEvent).order_by(NetworkPolicyEvent.event_id.desc()))
            self.assertEqual(latest.action,'REMOVED');self.assertTrue(json.loads(latest.previous_value)['enabled'])

    def test_duplicate_add_and_missing_id_do_not_overwrite_policy(self):
        self.apply('add',identifier='sim-a',cidr='192.0.2.0/24')
        with self.assertRaises(ManualTestGuardError):self.apply('add',identifier='sim-a',cidr='198.51.100.0/24')
        with self.assertRaises(ManualTestGuardError):self.apply('remove',identifier='not-present')
        self.assertEqual(self.n.request().json()['matched_policy_id'],'sim-a')

    def test_non_simulation_policies_are_not_mutable_by_test_manager(self):
        self.n.policy('unrelated','203.0.113.0/24',False)
        for command in ('set','enable','disable','remove'):
            with self.assertRaises(ManualTestGuardError):self.apply(command,identifier='unrelated',cidr='192.0.2.0/24')
        with self.n.f.sessions() as db:self.assertFalse(db.get(network.NetworkPolicy,'unrelated').enabled)

    def test_multi_cidr_login_profile_independent_after_one_is_disabled(self):
        self.apply('add',identifier='sim-a',cidr='192.0.2.0/24')
        self.apply('add',identifier='sim-b',cidr='198.51.100.0/24')
        self.apply('disable',identifier='sim-a')
        for source,result in [('192.0.2.10','FAIL'),('198.51.100.9','PASS'),('203.0.113.9','FAIL')]:
            client=TestClient(self.n.f.app,client=(source,1234))
            try:
                response=client.post('/login',json={'student_id':'DEVICE001','password':'test-password'})
                self.assertEqual(response.status_code,200)
                headers={'Authorization':'Bearer '+response.json()['access_token']}
                self.assertEqual(client.get('/me',headers=headers).status_code,200)
                self.assertEqual(client.post(network.PATH,headers=headers,json={}).json()['result'],result)
            finally:client.close()

    def test_id_scoped_restore_and_ipv6_range(self):
        self.apply('add',identifier='sim-v6',cidr='2001:db8:1::/48')
        with self.n.f.sessions() as db:saved={'format':'fyp-network-simulation-v1','policy':policy_state(db,'sim-v6')}
        self.apply('remove',identifier='sim-v6')
        self.apply('restore',identifier='sim-v6',snapshot=saved)
        self.assertEqual(self.n.request('2001:db8:1::9').json()['result'],'PASS')
        self.assertEqual(self.n.request('2001:db8:2::9').json()['result'],'FAIL')
        with self.assertRaises(ManualTestGuardError):self.apply('restore',identifier='different-id',snapshot=saved)

    def test_add_requires_explicit_simulation_and_id(self):
        for args in (['policy','add','--id','sim-a','--cidr','192.0.2.0/24'],
            ['policy','add','--cidr','192.0.2.0/24','--simulation']):
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:main(args)
            self.assertEqual(error.exception.code,2)


if __name__=='__main__':unittest.main()
