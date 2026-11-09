"""Offline target/credential/network guard checks; no database contact."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from cryptography.fernet import Fernet
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from manual_android_test import validate_profile,validate_lan_config,require_private_interface,select_private_interface,validate_native_config,ManualTestGuardError


def profile():
    return dict(db_host='127.0.0.1',db_port=3322,db_name='fypdevicemgmt_restore_abcdef123456',
        db_user='fyp_manual_runtime',db_password='isolated-test-only-'+('x'*32),
        expected_datadir='C:/FYP/DB-DeviceManagement/manual-android-test/data',
        biometric_key=Fernet.generate_key().decode(),timezone='Asia/Kuala_Lumpur',
        session_hours=8,challenge_seconds=90,face_threshold=0.45,
        demo_mode=False,fyp_account_bound_enrollment=True)


class ManualAndroidConfigTests(unittest.TestCase):
    def test_native_server_cannot_select_production_port_paths_or_init_file(self):
        env=Path('C:/FYP/DB-DeviceManagement/manual-android-fixture')
        content='[mysqld]\nport=3322\nbind-address=127.0.0.1\n'
        for key,name in {'basedir':'runtime','datadir':'data','tmpdir':'tmp','pid-file':'server.pid','secure-file-priv':'export'}.items():
            content+=key+'='+str(env/name)+'\n'
        content+='skip-slave-start\nskip-log-bin\nevent-scheduler=OFF\naria-recover-options=OFF\nmyisam-recover-options=OFF\nlocal-infile=0\ninnodb-buffer-pool-size=64M\ndefault-storage-engine=InnoDB\nmax-connections=30\nmax-statement-time=8\ncharacter-set-server=utf8mb4\ncollation-server=utf8mb4_general_ci\n'
        self.assertTrue(validate_native_config(content,env))
        for bad in (content.replace('port=3322','port=3306'),
            content.replace(str(env/'data'),'C:/xampp/mysql/data'),
            content+'init-file=C:/unreviewed.sql\n',content.replace('127.0.0.1','0.0.0.0')):
            with self.assertRaises(ManualTestGuardError):validate_native_config(bad,env)

    def test_lan_listener_requires_current_private_interface_and_matching_prefix(self):
        config=dict(address='192.168.0.162',subnet='192.168.0.0/24')
        for category,address,prefix,allowed in [('Private','192.168.0.162',24,True),
            ('Public','192.168.0.162',24,False),('Private','192.168.1.162',24,False),
            ('Private','192.168.0.162',16,False)]:
            result=SimpleNamespace(stdout=json.dumps(dict(category=category,address=address,prefix=prefix)))
            with patch('manual_android_test.subprocess.run',return_value=result):
                if allowed:require_private_interface(config)
                else:
                    with self.assertRaises(ManualTestGuardError):require_private_interface(config)

    def test_lan_requires_explicit_rfc1918_subnet(self):
        valid=dict(address='192.168.0.162',subnet='192.168.0.0/24')
        self.assertEqual(validate_lan_config(valid),valid)
        for change in ({'address':'0.0.0.0'},{'subnet':'0.0.0.0/0'},
            {'subnet':'192.0.0.0/8'},{'clients':['192.168.1.20']}):
            with self.assertRaises((ManualTestGuardError,ValueError)):validate_lan_config({**valid,**change})

    def test_lan_selection_has_no_per_device_configuration(self):
        row=dict(category='Private',address='172.20.16.5',prefix=20,interface='Wi-Fi')
        with patch('manual_android_test.private_interfaces',return_value=[row]):
            self.assertEqual(select_private_interface(),dict(address='172.20.16.5',subnet='172.20.16.0/20'))
        with patch('manual_android_test.private_interfaces',return_value=[row,{**row,'address':'172.20.16.6'}]):
            with self.assertRaises(ManualTestGuardError):select_private_interface()

    def test_explicit_disposable_profile(self):self.assertEqual(validate_profile(profile())['db_port'],3322)
    def test_production_endpoint_root_and_schema_rejected(self):
        for change in ({'db_port':3306},{'db_port':3307},{'db_host':'::1'},
            {'db_name':'attendance_proposal_xampp'},{'db_user':'root'}):
            with self.subTest(change=change),self.assertRaises(ManualTestGuardError):validate_profile({**profile(),**change})
    def test_production_data_directory_and_weak_secret_rejected(self):
        for change in ({'expected_datadir':'C:/xampp/mysql/data'}, {'db_password':''}):
            with self.assertRaises(ManualTestGuardError):validate_profile({**profile(),**change})
    def test_policy_and_algorithm_changes_rejected(self):
        for change in ({'demo_mode':True},{'fyp_account_bound_enrollment':False},{'face_threshold':0.9}):
            with self.assertRaises(ManualTestGuardError):validate_profile({**profile(),**change})
    def test_no_missing_or_extra_profile_fields(self):
        p=profile();p.pop('db_name')
        with self.assertRaises(ManualTestGuardError):validate_profile(p)
        with self.assertRaises(ManualTestGuardError):validate_profile({**profile(),'allow_production':True})
    def test_subprocess_guard_proves_ipv4_ipv6_localhost_denial_without_connecting(self):
        result=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve().parents[1]/'manual_android_test.py'),'--self-test'],
            capture_output=True,text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('IPv4, IPv6 and localhost',result.stdout)


if __name__=='__main__':unittest.main()
