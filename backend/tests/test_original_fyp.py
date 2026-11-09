"""Original setup integration with in-memory fixtures only; never connects to 3306."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import original_fyp as original
from application_schema import application_tables
from manual_android_test import ManualTestGuardError
from admin_testing import perform, document
from modules.networks.models import NetworkPolicy
from sqlalchemy import select
import test_admin_testing as admin


class OriginalGuards(unittest.TestCase):
    def test_boolean_reflection_accepts_only_tinyint_one_alias(self):
        from sqlalchemy import Table, MetaData, Column, Boolean, Integer, String
        from sqlalchemy.dialects.mysql import TINYINT
        from modules.devices.pending_migration import verify_table
        table = Table('sample', MetaData(), Column('enabled', Boolean, nullable=False))
        inspector = Mock()
        inspector.get_pk_constraint.return_value = {'constrained_columns': []}
        inspector.get_check_constraints.return_value = []
        inspector.get_indexes.return_value = []
        inspector.get_foreign_keys.return_value = []
        for kind, valid in ((TINYINT(display_width=1), True), (Boolean(), True),
                            (TINYINT(display_width=4), False), (Integer(), False), (String(1), False)):
            with self.subTest(kind=str(kind)):
                inspector.get_columns.return_value = [{'name': 'enabled', 'type': kind, 'nullable': False}]
                with patch('modules.devices.pending_migration.inspect', return_value=inspector):
                    if valid:
                        verify_table(Mock(), table)
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'Wrong type'):
                            verify_table(Mock(), table)

    def test_no_fallback_to_other_databases(self):
        for port, schema in ((3322, 'attendance_proposal_xampp'),
                             (3332, 'attendance_proposal_xampp'), (3306, 'another_schema')):
            fake = SimpleNamespace(db_host='127.0.0.1', db_port=port, db_name=schema, biometric_key='key')
            with patch('config.Settings', return_value=fake), self.assertRaises(ManualTestGuardError):
                original.settings()

    def test_canonical_inventory_has_43_tables_no_test_tables(self):
        tables = application_tables()
        self.assertEqual(len(tables), 43)
        self.assertEqual(len({t.name for t in tables}), 43)

    def test_failed_health_prevents_every_process_start(self):
        with patch.object(original, 'probe', side_effect=ManualTestGuardError('UNHEALTHY')), \
                patch('subprocess.Popen') as launch:
            with self.assertRaises(ManualTestGuardError):
                original.start()
            launch.assert_not_called()

    def test_readiness_rejects_other_backend_identity(self):
        actual = dict(version='test', port=3306, schema=original.TARGET[2])
        response = Mock(status_code=200)
        response.json.return_value = dict(environment='disposable', db_port=3322)
        client = Mock()
        client.__enter__ = Mock(return_value=client)
        client.__exit__ = Mock(return_value=False)
        client.get.return_value = response
        with patch.object(original, 'probe', return_value=actual), \
                patch('httpx.Client', return_value=client), self.assertRaises(ManualTestGuardError):
            original.backend_ready()

    def test_original_panel_label(self):
        page = document('Test', '')
        self.assertIn(b'FYP Attendance Management System', page.body)
        self.assertNotIn(b'database port 3306', page.body)
        self.assertNotIn(b'disposable testing', page.body)


class OriginalPanelIntegration(admin.AdminPanelTests):
    """Run all existing auth/CSRF/session/policy cases, with extra original-mode cases."""
    def test_original_policy_management_uses_existing_validator_and_audit(self):
        with self.f.sessions.begin() as db:
            perform(db, 'networks', dict(csrf='test', action='add', id='campus',
                name='Demo LAN', cidr='192.0.2.0/24'), 'operator', self.f.now,
                'Asia/Kuala_Lumpur', True, simulation_only=False)
        with self.f.sessions.begin() as db:
            perform(db, 'networks', dict(csrf='test', action='disable', id='campus'),
                    'operator', self.f.now, 'Asia/Kuala_Lumpur', True, simulation_only=False)
            self.assertFalse(db.get(NetworkPolicy, 'campus').enabled)
        with self.f.sessions.begin() as db, self.assertRaises(ValueError):
            perform(db, 'networks', dict(csrf='test', action='add', id='bad',
                name='Bad', cidr='not-an-ip'), 'operator', self.f.now,
                'Asia/Kuala_Lumpur', True, simulation_only=False)

    def test_original_mode_http_login_dashboard_session_and_policy(self):
        from admin_testing import create_panel
        from fastapi.testclient import TestClient
        panel = create_panel(self.engine, username='operator', password_hash=self.password_hash,
            ready=lambda: {'classroom_wifi': True}, now=lambda: self.f.now,
            database_port=3306, simulation_only=False)
        with TestClient(panel, base_url=admin.ORIGIN, client=('127.0.0.1', 3210),
                        follow_redirects=False) as client:
            self.client = client
            self.login()
            for area in ('sessions', 'networks', 'wifi', 'ble'):
                response = client.get('/' + area)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn('FYP Attendance Management System', response.text)
                if area == 'sessions':
                    self.assertIn('Students (read-only', response.text)
                    self.assertIn('DEVICE001', response.text)
            result = self.action('networks', action='add', id='real-format', name='Local LAN', cidr='192.0.2.0/24')
            self.assertEqual(result.status_code, 200, result.text)
            result = self.action('networks', action='disable', id='real-format')
            self.assertEqual(result.status_code, 200, result.text)
            self.close_fixture_windows()
            result = self.session()
            self.assertEqual(result.status_code, 200, result.text)
            self.assertIn('pin', result.json()['pin'])
    def test_shared_app_routes_registered_without_relaxing_authentication(self):
        from application_factory import create_app
        from fastapi.testclient import TestClient
        context = self.f.app.state.context
        app = create_app(settings=context.settings, engine=self.engine, biometrics=context.bio,
                         clock=context.now, classroom_features=True)
        paths = app.openapi()['paths']
        for path in ('/api/v1/classroom-wifi/classrooms', '/api/v1/classroom-ble/classrooms'):
            self.assertIn(path, paths)
            with TestClient(app) as client:
                self.assertEqual(client.get(path).status_code, 401)
        self.assertIsNotNone(app.state.context.classroom_attendance)
        self.assertFalse(hasattr(app.state.context, 'ble_attendance'))


if __name__ == '__main__':
    unittest.main()
