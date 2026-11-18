"""Offline staff portal tests. Uses only a disposable in-memory SQLite database."""
import re
import html
import json
import unittest
import asyncio
import threading
from contextlib import contextmanager
from unittest.mock import patch
from urllib.parse import urlencode
from html.parser import HTMLParser
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from models import (Attendance, AuthSession, Base, Challenge, ClassSchedule, ClassSession,
                    Course, Programme, Student, StudentGroup, VerificationAttempt)
from modules.networks.models import NetworkPolicy, NetworkPolicyEvent
from modules.classroom_wifi.models import Classroom, WifiPolicy, WifiPolicyEvent
from modules.classroom_ble.models import BlePolicy, BlePolicyEvent, BleEvent
from security import hash_password
from services.staff_attendance import StaffAttendanceError, mark_attendance
from services.attendance_timing import class_end, correction_deadline, finalize_due_attendance, run_absence_worker
from staff_portal import create_staff_portal

NOW = datetime(2026, 11, 18, 10, 0)


def fixture_engine():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
    tables = [Programme, StudentGroup, Student, Course, ClassSchedule, ClassSession,
              VerificationAttempt, Attendance, AuthSession, Challenge]
    Base.metadata.create_all(engine, tables=[model.__table__ for model in tables])
    for model in (NetworkPolicy, NetworkPolicyEvent, Classroom, WifiPolicy, WifiPolicyEvent,
                  BlePolicy, BlePolicyEvent, BleEvent):
        model.__table__.create(engine)
    with Session(engine) as db, db.begin():
        db.add(Programme(programme_code='CS', programme_name='Computer Science'))
        db.add(Course(course_code='CS101', course_name='Software Engineering', credit_hour=3))
        db.flush()
        db.add_all([StudentGroup(group_id=i, programme_code='CS', group_name=f'RSD{i}',
            year_of_study=3, semester=1, academic_year=2026) for i in (1, 2)])
        db.flush()
        db.add_all([Student(student_id=sid, group_id=group, name=name, email=sid+'@example.test',
            password_hash='unused', biometric_status='active', account_status='active', created_at=NOW)
            for sid, group, name in [('S001', 1, 'Aisha Tan'), ('S002', 1, 'Daniel Lee'), ('S003', 2, 'Other Group')]])
        db.add(ClassSchedule(schedule_id=1, course_code='CS101', group_id=1, day_of_week='Wednesday',
            class_type='Lecture', start_time=time(9), end_time=time(11), start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31), lecturer='Dr. Lim'))
        db.flush()
        db.add(ClassSession(session_id=1, schedule_id=1, session_date=NOW.date(), start_time=time(9),
            end_time=time(11), venue='K201', status='active', pin_hash='unused'))
    return engine


class PortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password('offline-test-password')

    def setUp(self):
        self.now = NOW
        self.engine = fixture_engine()
        self.app = FastAPI()
        self.app.mount('/portal', create_staff_portal(self.engine,
            credential_loader=lambda: dict(username='teacher', password_hash=self.password_hash),
            ready=lambda: {}, now=lambda: self.now))
        self.client = TestClient(self.app, base_url='http://127.0.0.1:8000', client=('127.0.0.1', 50000))
        self.client.__enter__()
        self.csrf = ''

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.engine.dispose()

    def login(self):
        response = self.client.get('/portal/login')
        self.assertIn('Welcome back.', response.text)
        self.assertIn('login-layout', response.text)
        self.csrf = re.search(r'name="csrf" value="([^"]+)"', response.text)[1]
        response = self.client.post('/portal/login', data=dict(csrf=self.csrf, username='teacher', password='offline-test-password'),
                                    headers={'Origin': 'http://127.0.0.1:8000'}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        response = self.client.get('/portal/dashboard')
        self.assertEqual(response.status_code, 200, response.text)
        self.csrf = re.search(r'name="csrf" value="([^"]+)"', response.text)[1]

    def mark(self, *, status='Present', version='unmarked', student='S001', reason='Seen in class by teacher'):
        response = self.client.post('/portal/actions/attendance', data=dict(csrf=self.csrf,
            session_id='1', student_id=student, status=status, reason=reason, version=version),
            headers={'Origin': 'http://127.0.0.1:8000', 'Accept': 'application/json'})
        if 'csrf' in response.json():
            self.csrf = response.json()['csrf']
        return response

    def test_protected_pages_and_exports_require_staff(self):
        for url in ['/portal/dashboard', '/portal/sessions', '/portal/attendance?session_id=1',
                    '/portal/students', '/portal/attendance/export?session_id=1',
                    '/portal/networks', '/portal/wifi', '/portal/ble']:
            response = self.client.get(url, follow_redirects=False)
            self.assertEqual(response.status_code, 303)
        self.assertEqual(self.mark().status_code, 401)

    def test_login_and_all_pages_render(self):
        self.login()
        for path in ['dashboard', 'sessions', 'attendance?session_id=1', 'students?q=Aisha', 'networks', 'wifi', 'ble']:
            response = self.client.get('/portal/' + path)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn('BioAttend', response.text)
            self.assertIn("frame-ancestors 'none'", response.headers['content-security-policy'])
        self.assertEqual(self.client.get('/portal/assets/portal.css').status_code, 200)
        self.assertEqual(self.client.get('/portal/assets/nope').status_code, 404)

    def test_present_then_absent_is_one_record_with_two_audits(self):
        self.login()
        self.assertEqual(self.mark().status_code, 200)
        with Session(self.engine) as db:
            record = db.scalar(select(Attendance))
            version = str(record.verification_id)
            self.assertEqual(record.status, 'Present')
            audit = db.get(VerificationAttempt, record.verification_id)
            self.assertEqual(audit.verification_result, 'manual_present')
            self.assertIsNone(audit.face_distance)
        self.assertEqual(self.mark(status='Absent', version=version, reason='Correction after checking register').status_code, 200)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Attendance)), 1)
            self.assertEqual(db.scalar(select(Attendance)).status, 'Absent')
            audits = db.scalars(select(VerificationAttempt).order_by(VerificationAttempt.verification_id)).all()
            self.assertEqual(len(audits), 2)
            self.assertEqual(audits[1].verification_result, 'manual_absent')
            self.assertIn('Staff: teacher; Present -> Absent', audits[1].failure_reason)

    def test_rejects_wrong_group_invalid_status_and_empty_reason(self):
        self.login()
        for args, expected in [({'student': 'S003'}, 403), ({'status': 'Excused'}, 400), ({'reason': ' '}, 400)]:
            self.assertEqual(self.mark(**args).status_code, expected)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Attendance)), 0)

    def test_stale_page_cannot_overwrite_an_attendance_record(self):
        self.login()
        self.assertEqual(self.mark().status_code, 200)
        self.assertEqual(self.mark(status='Absent').status_code, 409)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(Attendance)).status, 'Present')
            self.assertEqual(db.scalar(select(func.count()).select_from(VerificationAttempt)), 1)

    def test_csrf_wrong_origin_and_duplicate_fields_rejected(self):
        self.login()
        response = self.client.post('/portal/actions/attendance', data={'csrf': 'bad'},
            headers={'Origin': 'http://127.0.0.1:8000', 'Accept': 'application/json'})
        self.assertEqual(response.status_code, 403)
        response = self.client.post('/portal/logout', data={'csrf': self.csrf}, headers={'Origin': 'https://evil.test'})
        self.assertEqual(response.status_code, 403)
        response = self.client.post('/portal/logout', content=f'csrf={self.csrf}&csrf={self.csrf}',
            headers={'Origin': 'http://127.0.0.1:8000', 'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(response.status_code, 403)

    def test_lan_and_host_spoofing_cannot_access_portal(self):
        with TestClient(self.app, base_url='http://127.0.0.1:8000', client=('172.16.1.8', 1234)) as remote:
            self.assertEqual(remote.get('/portal/login').status_code, 403)
        self.assertEqual(self.client.get('/portal/login', headers={'Host': 'evil.test'}).status_code, 403)

    def test_cancelled_or_future_session_cannot_be_marked(self):
        self.login()
        with Session(self.engine) as db, db.begin():
            db.get(ClassSession, 1).status = 'cancelled'
        self.assertEqual(self.mark().status_code, 409)
        with Session(self.engine) as db, db.begin():
            s = db.get(ClassSession, 1)
            s.status, s.session_date = 'active', NOW.date() + timedelta(days=1)
        self.assertEqual(self.mark().status_code, 409)

    def test_absent_is_not_counted_as_attended_by_student_api(self):
        from api.attendance import classes, summary
        self.login()
        self.assertEqual(self.mark(status='Absent').status_code, 200)
        context = SimpleNamespace(now=lambda: NOW + timedelta(hours=2), settings=SimpleNamespace(demo_mode=False),
                                  session_open=lambda *_: False)
        with Session(self.engine) as db:
            identity = (db.get(Student, 'S001'), None)
            result = summary(identity=identity, db=db, context=context)
            self.assertEqual(result[0]['attended'], 0)
            self.assertEqual(result[0]['total'], 1)
            self.assertFalse(classes(identity=identity, db=db, context=context)[0]['attended'])

    def test_csv_export_includes_absence_and_protects_formulas(self):
        self.login()
        self.assertEqual(self.mark(status='Absent').status_code, 200)
        with Session(self.engine) as db, db.begin():
            db.get(Student, 'S001').name = '=FORMULA()'
        response = self.client.get('/portal/attendance/export?session_id=1')
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response.headers['content-disposition'])
        self.assertIn("'=FORMULA()", response.text)
        self.assertIn('Absent', response.text)
        self.assertIn('Teacher', response.text)

    def test_logout_invalidates_staff_session(self):
        self.login()
        self.assertEqual(self.client.post('/portal/logout', data={'csrf': self.csrf},
            headers={'Origin': 'http://127.0.0.1:8000'}, follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.get('/portal/dashboard', follow_redirects=False).status_code, 303)

    def test_closed_register_can_be_corrected_without_reopening_student_checkin(self):
        self.login()
        with Session(self.engine) as db, db.begin():
            db.get(ClassSession, 1).status = 'closed'
        self.assertEqual(self.mark(status='Absent').status_code, 200)
        with Session(self.engine) as db:
            self.assertEqual(db.get(ClassSession, 1).status, 'closed')

    def test_same_status_is_idempotent(self):
        self.login()
        self.assertEqual(self.mark().status_code, 200)
        with Session(self.engine) as db:
            version = str(db.scalar(select(Attendance)).verification_id)
        self.assertEqual(self.mark(version=version).status_code, 200)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(VerificationAttempt)), 1)

    def test_manual_record_cancels_pending_student_proof(self):
        with Session(self.engine) as db, db.begin():
            pending = VerificationAttempt(student_id='S001', session_id=1, stage='face',
                verification_result='pending', attempted_at=NOW)
            db.add(pending)
            db.add(AuthSession(token_hash='test-auth', student_id='S001', expires_at=NOW + timedelta(hours=1)))
            db.flush()
            pending_id = pending.verification_id
            db.add(Challenge(challenge_id='pending-proof', student_id='S001', session_id=1,
                auth_token_hash='test-auth', verification_id=pending_id, stage='face',
                expires_at=NOW + timedelta(minutes=1), consumed=False))
        self.login()
        self.assertEqual(self.mark(status='Absent').status_code, 200)
        with Session(self.engine) as db:
            self.assertTrue(db.get(Challenge, 'pending-proof').consumed)
            self.assertEqual(db.get(VerificationAttempt, pending_id).verification_result, 'cancelled')

    def test_session_pin_regenerate_and_close(self):
        self.login()
        for action in ['regenerate', 'close']:
            response = self.client.post('/portal/actions/sessions',
                data=dict(csrf=self.csrf, action=action, session_id='1'),
                headers={'Origin': 'http://127.0.0.1:8000', 'Accept': 'application/json'})
            self.assertEqual(response.status_code, 200, response.text)
            self.csrf = response.json()['csrf']
            if action == 'regenerate':
                self.assertRegex(response.json()['pin']['pin'], r'^\d{6}$')
        with Session(self.engine) as db:
            self.assertEqual(db.get(ClassSession, 1).status, 'closed')

    def test_create_session_reuses_existing_validation(self):
        self.login()
        with Session(self.engine) as db, db.begin():
            db.get(ClassSession, 1).status = 'closed'
        response = self.client.post('/portal/actions/sessions',
            data=dict(csrf=self.csrf, action='create', course_code='CS101', group_id='1', minutes='30', classroom_id=''),
            headers={'Origin': 'http://127.0.0.1:8000', 'Accept': 'application/json'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertRegex(response.json()['pin']['pin'], r'^\d{6}$')

    def test_consumed_csrf_cannot_be_replayed(self):
        self.login()
        stale_csrf = self.csrf
        self.assertEqual(self.mark().status_code, 200)
        self.csrf = stale_csrf
        self.assertEqual(self.mark(student='S002').status_code, 403)

    def test_root_redirects_to_portal_and_health_stays_json(self):
        from api.system import router
        self.app.state.staff_portal_enabled = True
        self.app.state.context = SimpleNamespace(settings=SimpleNamespace(demo_mode=False))
        self.app.include_router(router)
        response = self.client.get('/', follow_redirects=False)
        self.assertEqual(response.headers['location'], '/portal/')
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['message'], 'Backend running')

    def default_client(self, credential_loader=None):
        app = FastAPI()
        def missing_credentials():
            raise FileNotFoundError('No private account')
        app.mount('/portal', create_staff_portal(self.engine, ready=lambda: {}, now=lambda: self.now,
            credential_loader=credential_loader or missing_credentials, local_default_accounts=True))
        return TestClient(app, base_url='http://127.0.0.1:8000', client=('127.0.0.1', 50000))

    def authenticate_client(self, client, username, password):
        login = client.get('/portal/login')
        csrf = re.search(r'name="csrf" value="([^"]+)"', login.text)[1]
        return client.post('/portal/login', data=dict(csrf=csrf, username=username, password=password),
            headers={'Origin': 'http://127.0.0.1:8000'}, follow_redirects=False)

    def test_default_admin_and_teacher_work_without_private_credentials(self):
        for username, password, role in [('admin', 'Admin@123', 'Admin'), ('teacher', 'Teacher@123', 'Teacher')]:
            with self.subTest(role=role), self.default_client() as client:
                self.assertEqual(self.authenticate_client(client, username, password).status_code, 303)
                page = client.get('/portal/dashboard')
                self.assertEqual(page.status_code, 200)
                self.assertIn(f'class="staff-role">{role}</span>', page.text)
                for area in ('networks', 'wifi', 'ble'):
                    self.assertIn(f'href="/portal/{area}"', page.text)

    def test_default_teacher_can_mark_attendance_with_own_audit_identity(self):
        with self.default_client() as client:
            self.assertEqual(self.authenticate_client(client, 'teacher', 'Teacher@123').status_code, 303)
            register = client.get('/portal/attendance?session_id=1')
            csrf = re.search(r'name="csrf" value="([^"]+)"', register.text)[1]
            response = client.post('/portal/actions/attendance', data=dict(csrf=csrf, session_id='1',
                student_id='S001', status='Absent', reason='Absent during roll call', version='unmarked'),
                headers={'Origin': 'http://127.0.0.1:8000', 'Accept': 'application/json'})
            self.assertEqual(response.status_code, 200)
        with Session(self.engine) as db:
            audit = db.scalar(select(VerificationAttempt))
            self.assertIn('Staff: teacher;', audit.failure_reason)
            self.assertEqual(db.scalar(select(Attendance)).status, 'Absent')

    def test_wrong_default_password_and_student_account_are_rejected(self):
        with self.default_client() as client:
            for username, password in [('admin', 'wrong'), ('teacher', 'Admin@123'), ('S001', 'Teacher@123')]:
                self.assertEqual(self.authenticate_client(client, username, password).status_code, 401)

    def test_local_defaults_are_disabled_unless_explicitly_enabled(self):
        self.assertEqual(self.authenticate_client(self.client, 'admin', 'Admin@123').status_code, 401)
        self.assertEqual(self.authenticate_client(self.client, 'teacher', 'Teacher@123').status_code, 401)

    def test_custom_private_admin_still_works_alongside_defaults(self):
        loader = lambda: dict(username='localowner', password_hash=self.password_hash)
        with self.default_client(loader) as client:
            self.assertEqual(self.authenticate_client(client, 'localowner', 'offline-test-password').status_code, 303)
            self.assertIn('class="staff-role">Admin</span>', client.get('/portal/dashboard').text)

    def test_reserved_default_username_uses_default_password(self):
        loader = lambda: dict(username='admin', password_hash=self.password_hash)
        with self.default_client(loader) as client:
            self.assertEqual(self.authenticate_client(client, 'admin', 'Admin@123').status_code, 303)

    def policy_action(self, area, **data):
        response = self.client.post('/portal/actions/' + area, data=dict(csrf=self.csrf, **data),
            headers={'Origin': 'http://127.0.0.1:8000', 'Accept': 'application/json'})
        if 'csrf' in response.json():
            self.csrf = response.json()['csrf']
        return response

    def test_network_policy_add_and_disable_keep_audit(self):
        self.login()
        response = self.policy_action('networks', action='add', id='test-network', name='Class network', cidr='10.20.0.0/16')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.policy_action('networks', action='disable', id='test-network').status_code, 200)
        with Session(self.engine) as db:
            policy = db.get(NetworkPolicy, 'test-network')
            self.assertFalse(policy.enabled)
            self.assertEqual(policy.network_name, 'SIMULATION ONLY - Class network')
            self.assertEqual(db.scalar(select(func.count()).select_from(NetworkPolicyEvent)), 2)
        page = self.client.get('/portal/networks')
        self.assertIn('10.20.0.0/16', page.text)
        self.assertIn('Disabled', page.text)

    def test_non_simulation_network_remains_read_only_in_local_mode(self):
        with Session(self.engine) as db, db.begin():
            db.add(NetworkPolicy(network_id='campus', network_name='Campus', network_cidr='10.1.0.0/16',
                                 enabled=True, created_at=NOW, updated_at=NOW))
        self.login()
        self.assertIn('Read only', self.client.get('/portal/networks').text)
        self.assertEqual(self.policy_action('networks', action='disable', id='campus').status_code, 400)
        with Session(self.engine) as db:
            self.assertTrue(db.get(NetworkPolicy, 'campus').enabled)

    def test_invalid_network_is_rolled_back(self):
        self.login()
        self.assertEqual(self.policy_action('networks', action='add', id='bad', name='Bad', cidr='not-a-cidr').status_code, 400)
        with Session(self.engine) as db:
            self.assertIsNone(db.get(NetworkPolicy, 'bad'))
            self.assertEqual(db.scalar(select(func.count()).select_from(NetworkPolicyEvent)), 0)

    def test_wifi_policy_creates_room_and_toggles_with_audit(self):
        self.login()
        response = self.policy_action('wifi', action='add', id='ap-k201', classroom='K201', bssid='10:22:33:44:55:66', ssid='Campus')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.policy_action('wifi', action='disable', id='ap-k201').status_code, 200)
        self.assertEqual(self.policy_action('wifi', action='enable', id='ap-k201').status_code, 200)
        with Session(self.engine) as db:
            self.assertIsNotNone(db.get(Classroom, 'K201'))
            self.assertTrue(db.get(WifiPolicy, 'ap-k201').enabled)
            self.assertEqual(db.scalar(select(func.count()).select_from(WifiPolicyEvent)), 3)
        self.assertIn('10:22:33:44:55:66', self.client.get('/portal/wifi').text)

    def test_wifi_invalid_bssid_does_not_create_room(self):
        self.login()
        self.assertEqual(self.policy_action('wifi', action='add', id='bad-ap', classroom='BAD', bssid='02:00:00:00:00:00', ssid='').status_code, 400)
        with Session(self.engine) as db:
            self.assertIsNone(db.get(Classroom, 'BAD'))

    def test_ble_policy_starts_disabled_and_preserves_settings(self):
        self.login()
        response = self.policy_action('ble', action='add', id='beacon-k201', classroom='K201',
            uuid='b1ba7f4e-6931-49d5-99de-7e0caa159105', label='Teaching beacon',
            minimum_samples='5', threshold='-65', max_age_seconds='15')
        self.assertEqual(response.status_code, 200, response.text)
        with Session(self.engine) as db:
            self.assertFalse(db.get(BlePolicy, 'beacon-k201').enabled)
        self.assertEqual(self.policy_action('ble', action='enable', id='beacon-k201').status_code, 200)
        with Session(self.engine) as db:
            policy = db.get(BlePolicy, 'beacon-k201')
            self.assertTrue(policy.enabled)
            self.assertEqual((policy.minimum_samples, policy.rssi_threshold, policy.max_age_seconds), (5, -65, 15))
            self.assertTrue(policy.simulation_only)
            self.assertEqual(db.scalar(select(func.count()).select_from(BlePolicyEvent)), 2)
        page = self.client.get('/portal/ble')
        self.assertIn('Teaching beacon', page.text)
        self.assertIn('Attendance BLE shadow results', page.text)
        self.assertIn('Temporary Network + BLE Tests', page.text)

    def test_ble_diagnostic_history_is_visible_in_portal(self):
        with Session(self.engine) as db, db.begin():
            db.add(BleEvent(student_id='S001', challenge_id='nbt.1.offlinetest', classroom_id='K201',
                result='TEST_PASS', reason_code='NETWORK_BLE_TEST_PASSED', occurred_at=NOW))
        self.login()
        response = self.client.get('/portal/ble')
        self.assertEqual(response.status_code, 200)
        self.assertIn('NETWORK_BLE_TEST_PASSED', response.text)

    def test_teacher_can_view_policies_but_cannot_modify_them(self):
        with self.default_client() as client:
            self.assertEqual(self.authenticate_client(client, 'teacher', 'Teacher@123').status_code, 303)
            for area in ('networks', 'wifi', 'ble'):
                response = client.get('/portal/' + area)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn('Sign in as admin', response.text)
                self.assertNotIn(f'action="/portal/actions/{area}"', response.text)
                csrf = re.search(r'name="csrf" value="([^"]+)"', response.text)[1]
                response = client.post('/portal/actions/' + area, data=dict(csrf=csrf, action='disable', id='any'),
                    headers={'Origin': 'http://127.0.0.1:8000', 'Accept': 'application/json'})
                self.assertEqual(response.status_code, 403)

    def test_session_history_includes_pages_beyond_old_100_limit(self):
        with Session(self.engine) as db, db.begin():
            for index in range(2, 123):
                db.add(ClassSession(session_id=index, schedule_id=1, session_date=NOW.date() + timedelta(days=index),
                    start_time=time(9), end_time=time(11), venue='K201', status='active', pin_hash='unused'))
        self.login()
        response = self.client.get('/portal/sessions?history_page=3')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Page 3 of 3', response.text)
        self.assertIn('122 sessions', response.text)
        self.assertIn('Session #1', response.text)
        self.assertIn('history_page=2', response.text)

    def register_data(self, client=None):
        client = client or self.client
        response = client.get('/portal/attendance?session_id=1')
        self.assertEqual(response.status_code, 200, response.text)
        return dict(csrf=re.search(r'name="csrf" value="([^"]+)"', response.text)[1], session_id='1',
            roster=html.unescape(re.search(r'name="roster" value="([^"]+)"', response.text)[1]), reason='')

    def save_register(self, data, present=(), client=None, ajax=True):
        client = client or self.client
        pairs = list(data.items()) + [('present', sid) for sid in present]
        response = client.post('/portal/actions/attendance-register', content=urlencode(pairs),
            headers={'Origin': 'http://127.0.0.1:8000', 'Content-Type': 'application/x-www-form-urlencoded',
                     'Accept': 'application/json' if ajax else 'text/html'}, follow_redirects=False)
        if ajax and response.headers.get('content-type', '').startswith('application/json'):
            self.csrf = response.json().get('csrf', self.csrf)
        return response

    def test_attendance_entry_opens_class_sessions_first(self):
        self.login()
        response = self.client.get('/portal/attendance', follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers['location'], '/portal/sessions#session-list')
        response = self.client.get('/portal/sessions')
        self.assertIn('Open register', response.text)
        self.assertIn('href="/portal/attendance?session_id=1"', response.text)

    def test_register_shows_one_checkbox_per_enrolled_student_and_saves_nothing_on_get(self):
        self.login()
        response = self.client.get('/portal/attendance?session_id=1')
        boxes = re.findall(r'<input type="checkbox" name="present" value="([^"]+)"', response.text)
        self.assertEqual(set(boxes), {'S001', 'S002'})
        self.assertNotIn('Other Group', response.text)
        self.assertIn('Enrolled students', response.text)
        self.assertIn('Save attendance', response.text)
        self.assertNotIn('data-mark=', response.text)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Attendance)), 0)

    def test_checkbox_register_saves_ticked_present_and_unticked_absent(self):
        self.login()
        response = self.save_register(self.register_data(), present=['S001'])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((response.json()['present'], response.json()['absent'], response.json()['changed']), (1, 1, 2))
        with Session(self.engine) as db:
            self.assertEqual(dict(db.execute(select(Attendance.student_id, Attendance.status)).all()), {'S001': 'Present', 'S002': 'Absent'})
            audits = db.scalars(select(VerificationAttempt)).all()
            self.assertEqual(len(audits), 2)
            self.assertTrue(all('Staff: teacher;' in audit.failure_reason for audit in audits))

    def test_all_unchecked_can_mark_the_whole_class_absent(self):
        self.login()
        response = self.save_register(self.register_data())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((response.json()['present'], response.json()['absent']), (0, 2))
        with Session(self.engine) as db:
            self.assertEqual(list(db.scalars(select(Attendance.status))), ['Absent', 'Absent'])

    def test_multiple_ticked_students_are_accepted_without_javascript(self):
        self.login()
        response = self.save_register(self.register_data(), present=['S001', 'S002'], ajax=False)
        self.assertEqual(response.status_code, 303, response.text)
        self.assertEqual(response.headers['location'], '/portal/attendance?session_id=1')
        with Session(self.engine) as db:
            self.assertEqual(list(db.scalars(select(Attendance.status))), ['Present', 'Present'])

    def test_checked_biometric_and_late_records_keep_original_evidence(self):
        with Session(self.engine) as db, db.begin():
            for sid, status in [('S001', 'Present'), ('S002', 'Late')]:
                audit = VerificationAttempt(student_id=sid, session_id=1, stage='complete',
                    verification_result='success', attempted_at=NOW, face_distance=.25)
                db.add(audit)
                db.flush()
                db.add(Attendance(student_id=sid, session_id=1, verification_id=audit.verification_id,
                                  taken_at=NOW - timedelta(minutes=15), status=status))
        self.login()
        class CheckboxParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.boxes = {}
            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                if tag == 'input' and attributes.get('name') == 'present':
                    self.boxes[attributes['value']] = 'checked' in attributes
        parser = CheckboxParser()
        parser.feed(self.client.get('/portal/attendance?session_id=1').text)
        self.assertEqual(parser.boxes, {'S001': True, 'S002': True})
        response = self.save_register(self.register_data(), present=['S001', 'S002'])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['changed'], 0)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(VerificationAttempt)), 2)
            self.assertEqual(dict(db.execute(select(Attendance.student_id, Attendance.status)).all()), {'S001': 'Present', 'S002': 'Late'})
            self.assertTrue(all(record.taken_at == NOW - timedelta(minutes=15) for record in db.scalars(select(Attendance))))

    def test_register_stale_student_rolls_back_whole_save(self):
        self.login()
        data = self.register_data()
        self.assertEqual(self.mark(student='S002').status_code, 200)
        data['csrf'] = self.csrf
        response = self.save_register(data, present=['S001', 'S002'])
        self.assertEqual(response.status_code, 409, response.text)
        with Session(self.engine) as db:
            self.assertEqual(dict(db.execute(select(Attendance.student_id, Attendance.status)).all()), {'S002': 'Present'})
            self.assertEqual(db.scalar(select(func.count()).select_from(VerificationAttempt)), 1)

    def test_register_rejects_changed_enrollment(self):
        self.login()
        data = self.register_data()
        with Session(self.engine) as db, db.begin():
            db.add(Student(student_id='S004', group_id=1, name='New Enrolment', email='new@example.test',
                password_hash='unused', biometric_status='active', account_status='active', created_at=NOW))
        self.assertEqual(self.save_register(data, present=['S001']).status_code, 409)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Attendance)), 0)

    def test_register_rejects_foreign_and_duplicate_students(self):
        self.login()
        for selected in [['S003'], ['S001', 'S001']]:
            self.assertEqual(self.save_register(self.register_data(), present=selected).status_code, 400)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Attendance)), 0)

    def test_register_rejects_cancelled_and_future_class_sessions(self):
        self.login()
        data = self.register_data()
        for status, session_date in [('cancelled', NOW.date()), ('active', NOW.date() + timedelta(days=1))]:
            with Session(self.engine) as db, db.begin():
                session = db.get(ClassSession, 1)
                session.status, session.session_date = status, session_date
            data['csrf'] = self.csrf
            self.assertEqual(self.save_register(data, present=['S001']).status_code, 409)
            page = self.client.get('/portal/attendance?session_id=1')
            self.assertNotIn('>Save attendance</button>', page.text)

    def test_default_teacher_can_save_checkbox_register(self):
        with self.default_client() as client:
            self.assertEqual(self.authenticate_client(client, 'teacher', 'Teacher@123').status_code, 303)
            response = self.save_register(self.register_data(client), present=['S001'], client=client)
            self.assertEqual(response.status_code, 200, response.text)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Attendance)), 2)

    def test_large_class_checkbox_form_is_not_limited_to_8kb(self):
        with Session(self.engine) as db, db.begin():
            for index in range(4, 304):
                sid = f'S{index:04}'
                db.add(Student(student_id=sid, group_id=1, name=f'Enrolled student {index}', email=sid+'@example.test',
                    password_hash='unused', biometric_status='active', account_status='active', created_at=NOW))
        self.login()
        data = self.register_data()
        self.assertGreater(len(urlencode(data)), 8192)
        response = self.save_register(data, present=['S001'])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['total'], 302)

    def finalize(self, now):
        with Session(self.engine) as db, db.begin():
            return finalize_due_attendance(db, now=now)

    def test_automatic_absence_starts_at_class_end_and_is_idempotent(self):
        end = NOW.replace(hour=11)
        self.assertEqual(self.finalize(end - timedelta(microseconds=1)), 0)
        self.assertEqual(self.finalize(end), 2)
        self.assertEqual(self.finalize(end + timedelta(hours=6)), 0)
        with Session(self.engine) as db:
            self.assertEqual(list(db.scalars(select(Attendance.status))), ['Absent', 'Absent'])
            self.assertTrue(all(record.taken_at == end for record in db.scalars(select(Attendance))))
            audits = db.scalars(select(VerificationAttempt)).all()
            self.assertEqual(len(audits), 2)
            self.assertTrue(all(audit.stage == 'auto_absence' and audit.verification_result == 'auto_absent' for audit in audits))
            self.assertTrue(all(audit.face_distance is None for audit in audits))

    def test_automatic_absence_preserves_existing_present_and_teacher_corrections(self):
        self.login()
        self.assertEqual(self.mark().status_code, 200)
        self.assertEqual(self.finalize(NOW.replace(hour=11)), 1)
        with Session(self.engine) as db, db.begin():
            absent = db.scalar(select(Attendance).where(Attendance.student_id == 'S002'))
            mark_attendance(db, session_id=1, student_id='S002', status='Present', reason='Teacher corrected roll call',
                actor='teacher', version=str(absent.verification_id), now=NOW.replace(hour=12))
        self.assertEqual(self.finalize(NOW.replace(hour=16)), 0)
        with Session(self.engine) as db:
            self.assertEqual(list(db.scalars(select(Attendance.status))), ['Present', 'Present'])

    def test_catchup_after_server_downtime_records_absence_at_class_end(self):
        now = NOW + timedelta(days=2)
        self.assertEqual(self.finalize(now), 2)
        with Session(self.engine) as db:
            self.assertTrue(all(record.taken_at == NOW.replace(hour=11) for record in db.scalars(select(Attendance))))
            self.assertTrue(all(audit.attempted_at == now for audit in db.scalars(select(VerificationAttempt))))

    def test_cancelled_classes_do_not_generate_absence(self):
        with Session(self.engine) as db, db.begin():
            db.get(ClassSession, 1).status = 'cancelled'
        self.assertEqual(self.finalize(NOW.replace(hour=15)), 0)

    def test_closing_checkin_early_waits_until_scheduled_end_to_assign_absence(self):
        with Session(self.engine) as db, db.begin():
            db.get(ClassSession, 1).status = 'closed'
        self.assertEqual(self.finalize(NOW.replace(minute=30)), 0)
        self.assertEqual(self.finalize(NOW.replace(hour=11)), 2)

    def test_students_created_after_class_end_do_not_receive_historical_absence(self):
        with Session(self.engine) as db, db.begin():
            db.get(Student, 'S002').created_at = NOW.replace(hour=11, minute=1)
        self.assertEqual(self.finalize(NOW.replace(hour=15)), 1)
        with Session(self.engine) as db:
            self.assertEqual(list(db.scalars(select(Attendance.student_id))), ['S001'])

    def test_unknown_legacy_creation_date_does_not_crash_absence_processing(self):
        # MySQL returns None for imported zero dates. Simulate that conversion
        # when the worker loads a candidate after its date query.
        def unknown_date(student, _):
            if student.student_id == 'S002':
                from sqlalchemy.orm.attributes import set_committed_value
                set_committed_value(student, 'created_at', None)
        event.listen(Student, 'load', unknown_date)
        try:
            self.assertEqual(self.finalize(NOW.replace(hour=15)), 1)
        finally:
            event.remove(Student, 'load', unknown_date)
        with Session(self.engine) as db:
            self.assertEqual(list(db.scalars(select(Attendance.student_id))), ['S001'])

    def test_teacher_can_correct_until_one_microsecond_before_deadline(self):
        self.now = NOW.replace(hour=13) - timedelta(microseconds=1)
        self.login()
        data = self.register_data()
        response = self.save_register(data, present=['S001'])
        self.assertEqual(response.status_code, 200, response.text)
        with Session(self.engine) as db:
            self.assertEqual(dict(db.execute(select(Attendance.student_id, Attendance.status)).all()), {'S001': 'Present', 'S002': 'Absent'})

    def test_both_edit_routes_reject_exactly_two_hours_after_class_end(self):
        self.now = NOW.replace(hour=13)
        self.login()
        data = self.register_data()
        response = self.save_register(data, present=['S001'])
        self.assertEqual(response.status_code, 409, response.text)
        with Session(self.engine) as db:
            version = str(db.scalar(select(Attendance).where(Attendance.student_id == 'S001')).verification_id)
        self.assertEqual(self.mark(version=version).status_code, 409)
        with Session(self.engine) as db:
            self.assertEqual(list(db.scalars(select(Attendance.status))), ['Absent', 'Absent'])

    def test_ui_shows_automatic_source_and_locks_expired_register(self):
        self.now = NOW.replace(hour=12)
        self.login()
        response = self.client.get('/portal/attendance?session_id=1')
        self.assertIn('Automatic absence', response.text)
        self.assertIn('Teacher corrections close at 18 Nov 2026, 13:00', response.text)
        self.assertIn('Save attendance', response.text)
        self.now = NOW.replace(hour=13)
        response = self.client.get('/portal/attendance?session_id=1')
        self.assertIn('two-hour correction window ended', response.text)
        self.assertNotIn('>Save attendance</button>', response.text)
        self.assertEqual(len(re.findall(r'data-present-check\s+disabled', response.text)), 2)

    def test_correction_deadline_crosses_midnight(self):
        with Session(self.engine) as db, db.begin():
            session = db.get(ClassSession, 1)
            session.start_time, session.end_time = time(23), time(23, 30)
            self.assertEqual(correction_deadline(session), datetime(2026, 11, 19, 1, 30))
        self.now = datetime(2026, 11, 19, 1, 29, 59)
        self.login()
        self.assertEqual(self.save_register(self.register_data(), present=['S001']).status_code, 200)
        self.now = datetime(2026, 11, 19, 1, 30)
        self.assertEqual(self.save_register(self.register_data(), present=['S002']).status_code, 409)

    def test_save_crossing_the_deadline_rolls_back_before_commit(self):
        from services.staff_attendance import save_class_register
        self.now = NOW.replace(hour=12, minute=59, second=59)
        self.login()
        data = self.register_data()
        def crossing(*args, **kwargs):
            result = save_class_register(*args, **kwargs)
            self.now = NOW.replace(hour=13)
            return result
        with patch('staff_portal.save_class_register', side_effect=crossing):
            self.assertEqual(self.save_register(data, present=['S001']).status_code, 409)
        with Session(self.engine) as db:
            self.assertEqual(list(db.scalars(select(Attendance.status))), ['Absent', 'Absent'])
            self.assertEqual(db.scalar(select(func.count()).select_from(VerificationAttempt)), 2)

    def test_student_self_checkin_closes_at_class_end_without_using_staff_grace(self):
        from api.context import AppContext
        with Session(self.engine) as db:
            session, student = db.get(ClassSession, 1), db.get(Student, 'S001')
            context = SimpleNamespace(now=lambda: NOW.replace(hour=11) - timedelta(microseconds=1))
            self.assertTrue(AppContext.session_open(context, session, student, db))
            context.now = lambda: NOW.replace(hour=11)
            self.assertFalse(AppContext.session_open(context, session, student, db))
            context.now = lambda: NOW.replace(hour=12)
            self.assertFalse(AppContext.session_open(context, session, student, db))

    def test_student_history_and_summary_include_automatic_absence(self):
        from api.attendance import history, summary
        context = SimpleNamespace(now=lambda: NOW.replace(hour=11), automatic_absences=True,
            settings=SimpleNamespace(demo_mode=False, timezone='Asia/Kuala_Lumpur'))
        with Session(self.engine) as db, db.begin():
            identity = (db.get(Student, 'S001'), None)
            records = history(identity=identity, db=db, context=context)
            self.assertEqual([record['status'] for record in records], ['Absent'])
            totals = summary(identity=identity, db=db, context=context)
            self.assertEqual((totals[0]['total'], totals[0]['attended']), (1, 0))

    def test_background_worker_records_absences_without_any_http_request(self):
        completed = threading.Event()
        @contextmanager
        def tracked_session():
            with Session(self.engine) as db:
                yield db
            completed.set()
        context = SimpleNamespace(sessions=tracked_session, now=lambda: NOW.replace(hour=11))
        async def exercise():
            stop = asyncio.Event()
            task = asyncio.create_task(run_absence_worker(context, stop, interval=.01))
            try:
                self.assertTrue(await asyncio.to_thread(completed.wait, 5))
            finally:
                stop.set()
                await asyncio.wait_for(task, 5)
        asyncio.run(exercise())
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Attendance)), 2)

    def test_backend_lifespan_enables_absence_processing_and_closes_worker(self):
        from application_factory import create_app
        from config import Settings
        closed = []
        app = create_app(settings=Settings(biometric_key='offline-test-key'), engine=self.engine,
            biometrics=SimpleNamespace(close=lambda: closed.append(True)),
            clock=lambda: NOW.replace(hour=11), attendance_deadlines=True)
        with TestClient(app) as client:
            self.assertTrue(app.state.context.automatic_absences)
            with Session(self.engine) as db:
                self.assertEqual(db.scalar(select(func.count()).select_from(Attendance)), 2)
        self.assertEqual(closed, [True])


if __name__ == '__main__':
    unittest.main()
