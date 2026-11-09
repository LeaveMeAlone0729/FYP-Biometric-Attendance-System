"""Pure MySQL profile/guard tests: no database connections or service control."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cryptography.fernet import Fernet
from mysql_testing import validate_profile, BASE, identity
from database_compat import normalized_expression


class MySQLProfileTests(unittest.TestCase):
    def setUp(self):
        self.env=BASE/'env-0123456789ab'
        self.p=dict(format=1,vendor='mysql',version='8.4.3',server_uuid='12345678-1234-1234-1234-123456789abc',
            db_host='127.0.0.1',db_port=3332,db_name='fypmysqltest_0123456789ab',backend_port=8012,panel_port=8013,
            expected_datadir=str(self.env/'data'),expected_basedir=str(self.env/'runtime'),biometric_key=Fernet.generate_key().decode(),
            timezone='Asia/Kuala_Lumpur',session_hours=8,challenge_seconds=90,face_threshold=.45,demo_mode=False,fyp_account_bound_enrollment=True)
    def test_exact_profile_accepted(self):self.assertIs(validate_profile(self.p,self.env),self.p)
    def test_vendor_version_host_schema_directory_and_policy_mismatches_rejected(self):
        changes=[dict(vendor='mariadb'),dict(version='8.0.16'),dict(db_host='localhost'),dict(db_port=3306),
            dict(db_port=3322),dict(db_name='attendance_proposal_xampp'),dict(expected_datadir='C:/xampp/mysql/data'),
            dict(expected_basedir='C:/laragon/bin/mysql/mysql-8.4.3-winx64'),dict(server_uuid=''),dict(demo_mode=True),
            dict(fyp_account_bound_enrollment=False),dict(panel_port=8003),dict(backend_port=8013)]
        for patch in changes:
            with self.subTest(patch=list(patch)),self.assertRaises(RuntimeError):validate_profile({**self.p,**patch},self.env)
    def test_unknown_fields_rejected(self):
        with self.assertRaises(RuntimeError):validate_profile({**self.p,'skip_identity':True},self.env)
    def test_charset_reflection_normalization_keeps_checks(self):
        self.assertEqual(normalized_expression("status = _utf8mb4'ACTIVE'"),normalized_expression("status = 'ACTIVE'"))
        self.assertNotEqual(normalized_expression("slot IN (1,2)"),normalized_expression("slot IN (1,2,3)"))
    def test_actual_connection_identity_rejects_vendor_version_port_schema_account_uuid_and_paths(self):
        from unittest.mock import MagicMock
        row=['8.4.3','MySQL Community Server - GPL',3332,self.p['db_name'],'fyp_mysql_runtime@127.0.0.1',
            self.p['expected_datadir'],self.p['expected_basedir'],self.p['server_uuid']]
        c=MagicMock();c.execute.return_value.one.return_value=tuple(row)
        identity(c,self.p,'runtime')
        for index,bad in [(0,'10.4.27-MariaDB'),(0,'8.4.4'),(1,'MariaDB Server'),(2,3306),
                (3,'attendance_proposal_xampp'),(4,'root@localhost'),(5,'C:/xampp/mysql/data'),
                (6,'C:/laragon/bin/mysql'),(7,'different-instance')]:
            changed=row.copy();changed[index]=bad;c.execute.return_value.one.return_value=tuple(changed)
            with self.subTest(index=index,bad=bad),self.assertRaises(RuntimeError):identity(c,self.p,'runtime')
    def test_network_guard_blocks_ipv4_ipv6_localhost_production_before_connection(self):
        import subprocess
        script="""
import socket
from mysql_testing import network_guard
network_guard(3332)
for host in ('127.0.0.1','::1','localhost'):
 try:socket.create_connection((host,3306),timeout=.1)
 except PermissionError:continue
 raise RuntimeError('Production connect was not blocked before network access')
print('PASS')
"""
        result=subprocess.run([sys.executable,'-B','-c',script],cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,text=True,timeout=10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('PASS',result.stdout)


if __name__=='__main__':unittest.main()
