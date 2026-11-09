"""Synthetic operator sessions; no real students, keys or attendance writes."""
from pathlib import Path
from datetime import timedelta,datetime
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import json,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select,func
from models import ClassSession,ClassSchedule,Attendance,VerificationAttempt,Challenge,Student,AuthSession
from manual_sessions import create_session,list_sessions,close_session,require_backend_ready
from manual_android_test import ManualTestGuardError
from modules.authorization.service import AttendanceAuthorizationService
from modules.devices.service import DeviceRegistrationError
from security import digest,hash_password
import test_network_verification as network


class ManualSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.password_hash=hash_password('test-password')
    def setUp(self):
        self.n=network.NetworkTests();self.n.password_hash=self.password_hash
        if hasattr(self,'engine_override'):self.n.engine_override=self.engine_override
        self.n.setUp();self.sessions=self.n.f.sessions;self.now=self.n.f.now
        with self.sessions.begin() as db:
            for row in db.scalars(select(ClassSession).join(ClassSchedule).where(ClassSchedule.course_code=='DEMO101')):row.status='closed'
    def tearDown(self):self.n.tearDown()
    def create(self,**changes):
        with self.sessions.begin() as db:
            return create_session(db,**dict(now=self.now,timezone='Asia/Kuala_Lumpur',course_code='DEMO101',**changes))
    def close(self,identifier,**changes):
        with self.sessions.begin() as db:return close_session(db,session_id=identifier,now=self.now,timezone='Asia/Kuala_Lumpur',**changes)
    def test_generated_pin_is_hashed_and_not_in_session_list(self):
        result=self.create(minutes=30)
        self.assertRegex(result['pin'],r'^\d{6}$')
        with self.sessions() as db:
            row=db.get(ClassSession,result['session_id']);self.assertEqual(row.pin_hash,digest(result['pin']))
            self.assertNotEqual(row.pin_hash,result['pin'])
            listed=list_sessions(db,now=self.now,timezone='Asia/Kuala_Lumpur',course_code='DEMO101')
            self.assertEqual(len(listed),1);self.assertNotIn('pin',listed[0]);self.assertNotIn('pin_hash',listed[0])
    def test_explicit_expiry_converts_to_backend_timezone(self):
        result=self.create(expires_at=self.now.replace(hour=4,minute=45).isoformat()+'+00:00')
        self.assertTrue(result['expires_at'].endswith('12:45:00+08:00'))
    def test_bad_duration_expiry_and_midnight_are_rejected(self):
        for values in ({'minutes':0},{'minutes':-1},{'minutes':1441},{'expires_at':'bad'},
            {'expires_at':(self.now-timedelta(seconds=1)).isoformat()},
            {'expires_at':(self.now+timedelta(days=1)).isoformat()},
            {'minutes':30,'expires_at':self.now.isoformat()}):
            with self.subTest(values=values),self.assertRaises(ManualTestGuardError):self.create(**values)
    def test_missing_class_and_wrong_group_are_rejected(self):
        with self.sessions.begin() as db:
            with self.assertRaisesRegex(ManualTestGuardError,'CLASS_NOT_FOUND'):
                create_session(db,now=self.now,timezone='Asia/Kuala_Lumpur',course_code='UNKNOWN')
        with self.assertRaisesRegex(ManualTestGuardError,'CLASS_GROUP_NOT_FOUND'):self.create(group_id=99999)
    def test_overlap_rejected_without_replacing_first_session(self):
        result=self.create()
        with self.assertRaisesRegex(ManualTestGuardError,'SESSION_OVERLAP'):self.create(minutes=10)
        with self.sessions() as db:self.assertEqual(db.get(ClassSession,result['session_id']).pin_hash,digest(result['pin']))
    def test_close_preserves_history_and_allows_a_new_session(self):
        first=self.create()
        with self.sessions.begin() as db:
            root=VerificationAttempt(student_id='DEVICE001',session_id=first['session_id'],verification_result='success',stage='complete',attempted_at=self.now)
            db.add(root);db.flush()
            db.add(Attendance(student_id='DEVICE001',session_id=first['session_id'],verification_id=root.verification_id,taken_at=self.now,status='Present'))
        closed=self.close(first['session_id']);self.assertEqual(closed['attendance_count'],1)
        self.assertEqual(closed['starts_at'],first['starts_at']);self.assertEqual(closed['expires_at'],first['expires_at'])
        second=self.create();self.assertNotEqual(first['session_id'],second['session_id'])
        with self.sessions() as db:self.assertEqual(db.scalar(select(func.count()).select_from(Attendance)),1)
    def test_expire_is_safe_and_idempotent(self):
        first=self.create();self.assertTrue(self.close(first['session_id'],expire=True)['changed'])
        self.assertFalse(self.close(first['session_id'],expire=True)['changed'])
        with self.assertRaisesRegex(ManualTestGuardError,'SESSION_NOT_FOUND'):self.close(999999)
    def test_elapsed_sessions_hidden_but_available_in_all_listing(self):
        first=self.create(minutes=1)
        with self.sessions() as db:
            kwargs=dict(now=self.now+timedelta(minutes=2),timezone='Asia/Kuala_Lumpur',course_code='DEMO101')
            self.assertEqual(list_sessions(db,**kwargs),[])
            row=next(r for r in list_sessions(db,include_all=True,**kwargs) if r['session_id']==first['session_id'])
            self.assertEqual(row['window_state'],'EXPIRED')
    def test_stopped_backend_reports_actionable_error_without_http(self):
        with patch('prepare_manual_android_test.verified_pid',return_value=None),patch('httpx.get') as request:
            with self.assertRaisesRegex(ManualTestGuardError,'BACKEND_NOT_RUNNING'):require_backend_ready(Path('unused'))
            request.assert_not_called()
    def test_failed_transaction_does_not_create_a_session(self):
        with self.sessions() as db:before=db.scalar(select(func.count()).select_from(ClassSession))
        with self.assertRaisesRegex(RuntimeError,'synthetic rollback'):
            with self.sessions.begin() as db:
                create_session(db,now=self.now,timezone='Asia/Kuala_Lumpur',course_code='DEMO101')
                raise RuntimeError('synthetic rollback')
        with self.sessions() as db:self.assertEqual(db.scalar(select(func.count()).select_from(ClassSession)),before)
    def test_close_is_seen_by_attendance_boundary_even_with_cached_session(self):
        first=self.create()
        with self.sessions.begin() as db:
            root=VerificationAttempt(student_id='DEVICE001',session_id=first['session_id'],verification_result='pending',stage='face',attempted_at=self.now)
            db.add(root);db.flush()
            db.add(Challenge(challenge_id='isolated-close-test',student_id='DEVICE001',session_id=first['session_id'],
                auth_token_hash=digest(self.n.f.headers['Authorization'].split()[1]),verification_id=root.verification_id,
                stage='face',expires_at=self.now+timedelta(seconds=90)))
        with self.sessions() as pending:
            cached=pending.get(ClassSession,first['session_id']);self.assertEqual(cached.status,'active')
            self.close(first['session_id'])
            student=pending.get(Student,'DEVICE001');auth=pending.get(AuthSession,digest(self.n.f.headers['Authorization'].split()[1]))
            with self.assertRaises(DeviceRegistrationError) as error:
                AttendanceAuthorizationService(self.n.f.app.state.context).attempt(pending,student,auth,'isolated-close-test')
            self.assertEqual(error.exception.code,'ATTENDANCE_WINDOW_CLOSED')
    def test_concurrent_creations_serialize_on_group_in_mariadb(self):
        if self.n.f.engine.dialect.name!='mysql':self.skipTest('MariaDB row-lock integration only')
        def attempt(_):
            try:self.create();return 'CREATED'
            except ManualTestGuardError as exc:
                self.assertIn('SESSION_OVERLAP',str(exc));return 'OVERLAP'
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
        self.assertEqual(sorted(results),['CREATED','OVERLAP'])


if __name__=='__main__':unittest.main()
