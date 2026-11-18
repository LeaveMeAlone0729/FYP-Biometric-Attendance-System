"""Local HTML operator against disposable in-memory DBs; no real account/device changes."""
import re
import sys
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from admin_testing import create_panel, COOKIE
from admin_testing_launcher import backend_probe
from models import ClassSession, Attendance, Student, VerificationAttempt
from security import hash_password, digest
from manual_android_test import ManualTestGuardError
from modules.networks.models import NetworkPolicy, NetworkPolicyEvent
from modules.classroom_wifi.migration import upgrade as wifi_upgrade
from modules.classroom_wifi.models import WifiPolicy, Classroom, SessionClassroom
from modules.classroom_ble.migration import upgrade as ble_upgrade
from modules.classroom_ble.models import BlePolicy
import test_network_verification as network

ORIGIN = 'http://127.0.0.1:8003'
AJAX = {'Origin': ORIGIN, 'Accept': 'application/json'}
UUID = '7d9a6c10-326a-4c60-9e01-1ef000000001'


class AdminPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password('synthetic-admin-password')
        cls.student_hash = hash_password('test-password')

    def setUp(self):
        self.n = network.NetworkTests(); self.n.password_hash = self.student_hash
        if hasattr(self, 'engine_override'):
            self.n.engine_override = self.engine_override
        self.n.setUp()
        self.addCleanup(self.n.tearDown)
        self.f = self.n.f
        self.engine = self.f.sessions.kw['bind']
        wifi_upgrade(self.engine); ble_upgrade(self.engine)
        self.ticks = 0
        self.available = True
        self.capabilities = {'classroom_wifi': True}
        def ready():
            if not self.available:
                raise ManualTestGuardError('BACKEND_NOT_READY')
            return self.capabilities
        self.app = create_panel(self.engine, username='operator', password_hash=self.password_hash,
            ready=ready, now=lambda: self.f.now, clock=lambda: self.ticks)
        self.client = TestClient(self.app, base_url=ORIGIN, client=('127.0.0.1', 4567), follow_redirects=False)
        self.addCleanup(self.client.close)

    def csrf(self, response):
        return re.search(r'name="csrf" value="([^"]+)"', response.text).group(1)

    def login(self):
        response = self.client.get('/login')
        old = self.client.cookies.get(COOKIE)
        result = self.client.post('/login', data={'csrf': self.csrf(response), 'username': 'operator',
            'password': 'synthetic-admin-password'}, headers={'Origin': ORIGIN})
        self.assertEqual(result.status_code, 303, result.text)
        self.assertNotEqual(old, self.client.cookies.get(COOKIE))

    def action(self, area, **data):
        page = self.client.get('/' + area)
        self.assertEqual(page.status_code, 200, page.text)
        result = self.client.post('/actions/' + area, data={'csrf': self.csrf(page), **data}, headers=AJAX)
        self.assertNotIn('location', result.headers)
        self.assertIn('message', result.json())
        self.assertEqual(result.headers['cache-control'], 'no-store')
        return result

    def session(self, **overrides):
        data = dict(action='create', course_code='DEMO101', group_id='', minutes='30', classroom_id='')
        data.update(overrides)
        return self.action('sessions', **data)

    def close_fixture_windows(self):
        with self.f.sessions.begin() as db:
            for s in db.scalars(select(ClassSession)):
                s.status = 'closed'

    def test_admin_login_logout_revocation_and_student_credentials_rejected(self):
        page = self.client.get('/login')
        self.assertEqual(self.client.post('/login', headers={'Origin': ORIGIN}, data={
            'csrf': self.csrf(page), 'username': 'DEVICE001', 'password': 'test-password'}).status_code, 401)
        self.login()
        page = self.client.get('/sessions')
        self.assertEqual(page.status_code, 200)
        token = self.client.cookies.get(COOKIE)
        result = self.client.post('/logout', data={'csrf': self.csrf(page)}, headers={'Origin': ORIGIN})
        self.assertEqual(result.status_code, 303)
        self.client.cookies.set(COOKIE, token)
        self.assertEqual(self.client.get('/sessions').status_code, 303)

    def test_both_local_hosts_login_and_redirect_to_real_dashboard(self):
        for host in ('127.0.0.1', 'localhost'):
            origin = f'http://{host}:8003'
            with self.subTest(host=host), TestClient(self.app, base_url=origin,
                    client=('127.0.0.1', 4567), follow_redirects=False) as client:
                page = client.get('/login')  # Ordinary GET has no Origin or Referer.
                self.assertEqual(page.status_code, 200)
                self.assertEqual(page.headers['referrer-policy'], 'same-origin')
                self.assertIn('method="post" action="/login"', page.text)
                response = client.post('/login', data={'csrf': self.csrf(page), 'username': 'operator',
                    'password': 'synthetic-admin-password'}, headers={'Origin': origin, 'Referer': origin + '/login'})
                self.assertEqual(response.status_code, 303, response.text)
                self.assertEqual(response.headers['location'], '/sessions')
                dashboard = client.get(response.headers['location'])  # Redirected GET needs no Origin.
                self.assertEqual(dashboard.status_code, 200)
                self.assertIn('<h1>Attendance Sessions</h1>', dashboard.text)
                self.assertIn('Create Session', dashboard.text)
                self.assertIn('aria-current="page"', dashboard.text)
                self.assertIn('HttpOnly', response.headers['set-cookie'])
                self.assertIn('SameSite=strict', response.headers['set-cookie'])

    def test_login_keeps_exact_origin_check_and_requires_csrf(self):
        for origin in ('null', 'http://evil.invalid', 'http://127.0.0.1:8002', 'http://localhost:8003', None):
            page = self.client.get('/login')
            headers = {'Referer': ORIGIN + '/login'}  # Referer cannot override invalid/missing Origin.
            if origin is not None: headers['Origin'] = origin
            result = self.client.post('/login', data={'csrf': self.csrf(page), 'username': 'operator',
                'password': 'synthetic-admin-password'}, headers=headers)
            self.assertEqual(result.status_code, 403, result.text)
            self.assertEqual(result.text, 'Origin rejected.')
        for csrf in (None, 'forged-token'):
            self.client.get('/login')
            data = {'username': 'operator', 'password': 'synthetic-admin-password'}
            if csrf is not None: data['csrf'] = csrf
            result = self.client.post('/login', data=data, headers={'Origin': ORIGIN})
            self.assertEqual(result.status_code, 403)
            self.assertIn('CSRF rejected', result.text)

    def test_every_management_page_and_mutation_requires_admin(self):
        for area in ('sessions', 'networks', 'wifi', 'ble'):
            self.assertEqual(self.client.get('/' + area).status_code, 303)
            response = self.client.post('/actions/' + area, data={'csrf': 'forged', 'action': 'add'}, headers={'Origin': ORIGIN})
            self.assertEqual(response.status_code, 401)
        self.client.cookies.set(COOKIE, 'forged-admin-cookie')
        self.assertEqual(self.client.get('/sessions').status_code, 303)
        for path in ('/docs', '/openapi.json', '/login/student', '/liveness/frame', '/api/v1/devices'):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_csrf_missing_forged_duplicate_and_cross_origin_rejected(self):
        self.login(); token = self.csrf(self.client.get('/sessions'))
        for headers, body in [({'Origin': ORIGIN}, {'csrf': 'bad'}),
                ({'Origin': ORIGIN, 'Content-Type': 'application/x-www-form-urlencoded'}, {}), ({'Origin': 'http://evil.invalid'}, {'csrf': token}),
                ({}, {'csrf': token}), ({'Origin': ORIGIN}, {'csrf': [token, token]})]:
            self.assertEqual(self.client.post('/actions/sessions', data=body, headers=headers).status_code, 403)
        self.assertEqual(self.client.post('/logout', data={}, headers={'Origin': ORIGIN, 'Content-Type': 'application/x-www-form-urlencoded'}).status_code, 403)

    def test_loopback_host_and_forwarding_guards(self):
        self.assertEqual(self.client.get('/login', headers={'Host': 'evil.invalid'}).status_code, 403)
        remote = TestClient(self.app, base_url=ORIGIN, client=('192.0.2.1', 3))
        try:
            self.assertEqual(remote.get('/login', headers={'X-Forwarded-For': '127.0.0.1', 'CF-Connecting-IP': '127.0.0.1'}).status_code, 403)
        finally:
            remote.close()
        self.assertEqual(self.client.get('/login', headers={'X-Forwarded-For': '192.0.2.1'}).status_code, 200)

    def test_session_expiry_and_fixed_login_throttle(self):
        self.login(); self.ticks += 1801
        self.assertEqual(self.client.get('/sessions').status_code, 303)
        for i in range(6):
            page = self.client.get('/login')
            result = self.client.post('/login', data={'csrf': self.csrf(page), 'username': 'operator', 'password': 'wrong'}, headers={'Origin': ORIGIN})
            self.assertEqual(result.status_code, 401 if i < 5 else 429)

    def test_pin_once_session_duration_close_and_unchanged_attendance(self):
        self.close_fixture_windows(); self.login()
        page = self.client.get('/sessions'); csrf = self.csrf(page)
        data = dict(csrf=csrf, action='create', course_code='DEMO101', group_id='', minutes='20', classroom_id='')
        result = self.client.post('/actions/sessions', data=data, headers={'Origin': ORIGIN})
        self.assertEqual(result.status_code, 200, result.text)
        pin = re.search(r'PIN: <strong>(\d{6})</strong>', result.text).group(1)
        self.assertEqual(result.headers['cache-control'], 'no-store')
        with self.f.sessions() as db:
            row = db.scalar(select(ClassSession).where(ClassSession.pin_hash == digest(pin)))
            identifier = row.session_id
            self.assertEqual(row.end_time.hour * 60 + row.end_time.minute - row.start_time.hour * 60 - row.start_time.minute, 20)
        self.assertEqual(self.client.post('/actions/sessions', data=data, headers={'Origin': ORIGIN}).status_code, 403)
        listed = self.client.get('/sessions')
        self.assertNotIn(pin, listed.text); self.assertNotIn(digest(pin), listed.text)
        closed = self.client.post('/actions/sessions', headers={'Origin': ORIGIN},
            data=dict(csrf=self.csrf(listed), action='close', session_id=str(identifier)))
        self.assertEqual((closed.status_code, closed.headers['location']), (303, '/sessions'))
        with self.f.sessions() as db:
            self.assertEqual(db.get(ClassSession, identifier).status, 'closed')
            self.assertEqual(db.scalar(select(func.count()).select_from(Attendance)), 0)

    def test_ajax_pin_regeneration_replaces_hash_and_preserves_session(self):
        self.close_fixture_windows(); self.login()
        created = self.session()
        self.assertEqual(created.status_code, 200, created.text)
        old = created.json()['pin']
        identifier = old['session_id']
        with self.f.sessions.begin() as db:
            db.get(Student, 'DEVICE001').biometric_status = 'active'
            attempt = VerificationAttempt(student_id='DEVICE002', session_id=identifier,
                verification_result='success', stage='complete', attempted_at=self.f.now)
            db.add(attempt)
            db.flush()
            attendance = Attendance(student_id='DEVICE002', session_id=identifier,
                verification_id=attempt.verification_id, status='Present', taken_at=self.f.now)
            db.add(attendance)
            db.flush()
            attendance_id = attendance.attendance_id
        page = self.client.get('/sessions')
        self.assertIn('Regenerate PIN', page.text)
        self.assertIn('data-confirm-title="Regenerate PIN"', page.text)
        self.assertIn('data-confirm-title="Close Session"', page.text)
        self.assertIn('<span class="badge positive">OPEN</span>', page.text)
        self.assertIn('id="action-pin" class="pin-card" aria-labelledby="pin-title" hidden', page.text)
        self.assertNotIn('<details>', page.text)
        self.assertNotIn(old['pin'], page.text)
        self.assertNotIn(digest(old['pin']), page.text)
        action = dict(action='regenerate', session_id=str(identifier))
        denied = self.action('sessions', **action, confirm='no')
        self.assertEqual(denied.status_code, 400)
        self.assertNotIn('pin', denied.json())
        self.assertIn('CONFIRMATION_REQUIRED', denied.json()['message'])
        with self.f.sessions() as db:
            self.assertEqual(db.get(ClassSession, identifier).pin_hash, digest(old['pin']))
        original_request = dict(csrf=denied.json()['csrf'], **action, confirm='yes')
        rotated = self.client.post('/actions/sessions', data=original_request, headers=AJAX)
        self.assertEqual(rotated.status_code, 200, rotated.text)
        new = rotated.json()['pin']
        self.assertNotEqual(old['pin'], new['pin'])
        self.assertEqual(old['session_id'], new['session_id'])
        self.assertEqual(old['expires_at'], new['expires_at'])
        self.assertEqual(self.client.post('/actions/sessions', data=original_request,
            headers=AJAX).status_code, 403)
        with self.f.sessions() as db:
            self.assertEqual(db.get(ClassSession, identifier).pin_hash, digest(new['pin']))
            saved = db.get(Attendance, attendance_id)
            self.assertEqual((saved.student_id, saved.session_id, saved.status, saved.taken_at),
                ('DEVICE002', identifier, 'Present', self.f.now))
        rejected = self.f.client.post('/attendance/start', json={'pin': old['pin']}, headers=self.f.headers)
        self.assertEqual(rejected.status_code, 400)
        self.assertIn('PIN does not match', rejected.text)
        accepted = self.f.client.post('/attendance/start', json={'pin': new['pin']}, headers=self.f.headers)
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()['session_id'], identifier)
        page = self.client.get('/sessions')
        self.assertNotIn(new['pin'], page.text)
        self.assertEqual(self.action('sessions', action='close', session_id=str(identifier)).status_code, 200)
        self.assertIn('<span class="badge neutral">CLOSED</span>', self.client.get('/sessions').text)
        blocked = self.action('sessions', **action, confirm='yes')
        self.assertEqual(blocked.status_code, 400)
        self.assertNotIn('pin', blocked.json())

    def test_pin_regeneration_requires_admin_csrf_and_open_window(self):
        self.close_fixture_windows(); self.login()
        pin = self.session(minutes='1').json()['pin']
        data = dict(action='regenerate', session_id=str(pin['session_id']), confirm='yes')
        response = self.client.post('/actions/sessions', data={**data, 'csrf': 'bad'}, headers=AJAX)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('pin', response.json())
        self.f.now += timedelta(minutes=2)
        page = self.client.get('/sessions')
        self.assertNotIn('Regenerate PIN', page.text)
        self.assertIn('<span class="badge warning">EXPIRED</span>', page.text)
        response = self.action('sessions', **data)
        self.assertEqual(response.status_code, 400)
        self.assertIn('SESSION_NOT_OPEN', response.json()['message'])
        self.assertNotIn('pin', response.json())
        self.ticks += 1801
        response = self.client.post('/actions/sessions', data={**data, 'csrf': response.json()['csrf']}, headers=AJAX)
        self.assertEqual(response.status_code, 401)
        self.assertNotIn('pin', response.json())
        with self.f.sessions() as db:
            self.assertEqual(db.get(ClassSession, pin['session_id']).pin_hash, digest(pin['pin']))

    def test_management_script_is_same_origin_and_pages_have_inline_targets(self):
        self.login()
        script = self.client.get('/admin-testing.js')
        self.assertEqual(script.status_code, 200)
        self.assertIn('text/javascript', script.headers['content-type'])
        self.assertIn('if (pending || dialog.open) return', script.text)
        stylesheet = self.client.get('/admin-testing.css')
        self.assertEqual(stylesheet.status_code, 200)
        self.assertIn('text/css', stylesheet.headers['content-type'])
        for area in ('sessions', 'networks', 'wifi', 'ble'):
            page = self.client.get('/' + area)
            self.assertIn('id="action-status" role="status"', page.text)
            self.assertIn('id="management-table"', page.text)
            self.assertIn('<dialog id="confirmation"', page.text)
            self.assertIn('href="/admin-testing.css"', page.text)
            self.assertIn(f'action="/actions/{area}"', page.text)
            self.assertIn('script-src \'self\'; connect-src \'self\'', page.headers['content-security-policy'])
            self.assertIn("style-src 'self'", page.headers['content-security-policy'])

    def test_classroom_assignment_only_existing_and_integrated(self):
        self.close_fixture_windows(); self.login()
        self.assertEqual(self.session(classroom_id='UNKNOWN').status_code, 400)
        with self.f.sessions.begin() as db:
            db.add(Classroom(classroom_id='A', name='Room A', created_at=self.f.now))
        self.capabilities = {'classroom_wifi': False}
        self.assertEqual(self.session(classroom_id='A').status_code, 400)
        self.capabilities = {'classroom_wifi': True}
        result = self.session(classroom_id='A')
        self.assertEqual(result.status_code, 200, result.text)
        with self.f.sessions() as db:
            self.assertEqual(db.scalar(select(SessionClassroom)).classroom_id, 'A')

    def test_validation_overlap_and_stopped_backend_do_not_insert(self):
        self.login()
        self.assertEqual(self.session().status_code, 400)  # Existing synthetic window overlaps.
        for values in ({'minutes': '0'}, {'minutes': 'bad'}, {'course_code': 'missing'}):
            data = dict(action='create', course_code='DEMO101', group_id='', minutes='30', classroom_id='')
            data.update(values)
            self.assertEqual(self.action('sessions', **data).status_code, 400)
        self.available = False
        self.assertEqual(self.client.get('/sessions').status_code, 503)
        with self.f.sessions() as db:
            before = db.scalar(select(func.count()).select_from(ClassSession))
        # Obtain a valid token from the error page; readiness still blocks mutation.
        csrf = self.csrf(self.client.get('/sessions'))
        self.assertEqual(self.client.post('/actions/sessions', data=dict(csrf=csrf, action='close', session_id='1'), headers={'Origin': ORIGIN}).status_code, 503)
        with self.f.sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(ClassSession)), before)

    def test_network_management_existing_validator_and_simulation_boundary(self):
        self.login()
        self.assertEqual(self.action('networks', action='add', id='v4', name='Synthetic home', cidr='192.0.2.0/24').status_code, 200)
        self.assertEqual(self.action('networks', action='add', id='v6', name='Synthetic IPv6', cidr='2001:db8::/64').status_code, 200)
        self.assertEqual(self.action('networks', action='disable', id='v4').status_code, 200)
        with self.f.sessions() as db:
            self.assertFalse(db.get(NetworkPolicy, 'v4').enabled)
        self.assertEqual(self.action('networks', action='enable', id='v4').status_code, 200)
        self.assertEqual(self.action('networks', action='add', id='bad', name='Invalid', cidr='not-cidr').status_code, 400)
        with self.f.sessions() as db:
            self.assertIsNone(db.get(NetworkPolicy, 'bad'))
            self.assertEqual(db.scalar(select(func.count()).select_from(NetworkPolicyEvent)), 4)
        self.n.policy(identifier='external')
        self.assertEqual(self.action('networks', action='disable', id='external').status_code, 400)

    def test_wifi_management_escapes_html_and_keeps_validation(self):
        self.login()
        values = dict(action='add', id='ap1', classroom='A', bssid='d8:42:a1:9e:de:2f', ssid='<script>bad</script>')
        self.assertEqual(self.action('wifi', **values).status_code, 200)
        page = self.client.get('/wifi')
        self.assertIn('&lt;script&gt;bad&lt;/script&gt;', page.text)
        self.assertNotIn('<script>', page.text)
        self.assertEqual(self.action('wifi', action='disable', id='ap1').status_code, 200)
        self.assertEqual(self.action('wifi', action='enable', id='ap1').status_code, 200)
        values.update(id='bad', bssid='02:00:00:00:00:00')
        self.assertEqual(self.action('wifi', **values).status_code, 400)
        with self.f.sessions() as db:
            self.assertTrue(db.get(WifiPolicy, 'ap1').enabled)
            self.assertIsNone(db.get(WifiPolicy, 'bad'))

    def test_ble_management_disabled_default_experimental_only(self):
        self.login()
        values = dict(action='add', id='beacon1', classroom='A', uuid=UUID, label='', minimum_samples='5', threshold='-65', max_age_seconds='15')
        self.assertEqual(self.action('ble', **values).status_code, 200)
        with self.f.sessions() as db:
            self.assertFalse(db.get(BlePolicy, 'beacon1').enabled)
        self.assertIn('NOT enforced by attendance', self.client.get('/ble').text)
        self.assertEqual(self.action('ble', action='enable', id='beacon1').status_code, 200)
        self.assertEqual(self.action('ble', action='disable', id='beacon1').status_code, 200)
        values.update(id='bad', uuid='invalid')
        self.assertEqual(self.action('ble', **values).status_code, 400)
        with self.f.sessions() as db:
            self.assertFalse(db.get(BlePolicy, 'beacon1').enabled)
            self.assertEqual(db.scalar(select(func.count()).select_from(Attendance)), 0)

    def test_unknown_actions_extra_fields_and_large_forms_rejected(self):
        self.login()
        self.assertEqual(self.action('networks', action='delete', id='anything').status_code, 400)
        self.assertEqual(self.action('networks', action='enable', id='anything', admin='true').status_code, 400)
        self.assertEqual(self.client.post('/actions/networks', headers={'Origin': ORIGIN}, data={'blob': 'x' * 9000}).status_code, 413)
        self.assertEqual(self.client.post('/actions/networks', headers={'Origin': ORIGIN}, json={}).status_code, 415)

    def test_missing_optional_schema_is_unavailable_without_auto_migration(self):
        self.login()
        with patch('admin_testing.inspect') as inspector:
            inspector.return_value.get_table_names.return_value = []
            self.assertEqual(self.client.get('/ble').status_code, 503)
        self.assertEqual(self.action('networks', action='add', id='v4', name='Still works', cidr='192.0.2.0/24').status_code, 200)

    def test_backend_probe_rejects_ordinary_port8000_missing_isolation_contract(self):
        import httpx
        with patch('httpx.Client') as client:
            client.return_value.__enter__.return_value.get.side_effect = httpx.ConnectError('offline')
            with self.assertRaises(ManualTestGuardError): backend_probe(8000)
        with self.assertRaises(ManualTestGuardError): backend_probe(3306)
        with patch('prepare_manual_android_test.verified_pid', return_value=None), patch('httpx.Client') as client:
            with self.assertRaises(ManualTestGuardError): backend_probe(8002, environment=Path('synthetic'))
            client.assert_not_called()

    def test_database_error_rolls_back_and_does_not_expose_connection_secrets(self):
        from sqlalchemy.exc import OperationalError
        self.login(); page = self.client.get('/networks')
        with patch('admin_testing.perform', side_effect=OperationalError('secret SQL', {}, Exception('password secret'))):
            r = self.client.post('/actions/networks', data=dict(csrf=self.csrf(page), action='add', id='x', name='X', cidr='192.0.2.0/24'), headers=AJAX)
        self.assertEqual(r.status_code, 503)
        self.assertNotIn('password secret', r.text)
        self.assertIn('csrf', r.json())
        with self.f.sessions() as db:
            self.assertIsNone(db.get(NetworkPolicy, 'x'))

    def test_admin_initialization_hash_only_and_no_overwrite_or_database_connection(self):
        import tempfile, json, contextlib, io
        from admin_testing_launcher import main, credentials
        from security import verify_password
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with patch('manual_android_test.load_profile', return_value={}), patch('builtins.input', return_value='operator'), \
                    patch('getpass.getpass', return_value='synthetic-local-secret'), patch('fyp_test.operator_engine') as db, \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(['--environment', str(path), '--init-admin']), 0)
                original = (path / 'panel-admin.json').read_bytes()
                self.assertEqual(main(['--environment', str(path), '--init-admin']), 1)
                self.assertEqual((path / 'panel-admin.json').read_bytes(), original)
                db.assert_not_called()
            self.assertNotIn('synthetic-local-secret', original.decode())
            self.assertNotIn('synthetic-local-secret', output.getvalue())
            self.assertTrue(verify_password('synthetic-local-secret', credentials(path / 'panel-admin.json')['password_hash']))


if __name__ == '__main__':
    unittest.main()
