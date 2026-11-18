"""Startup regressions: temp credential files, no persistent DB access or passwords in output."""
import contextlib
import getpass
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from admin_testing_launcher import main, initialize_admin, credentials
from manual_android_test import ManualTestGuardError
from security import verify_password


class AdminLauncherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env = Path(self.directory.name)
        self.path = self.env / 'panel-admin.json'

    def invoke(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(['--environment', str(self.env), *args])
        return code, output.getvalue()

    def test_short_password_and_confirmation_mismatch_can_be_corrected(self):
        secret = 'synthetic-local-password'
        output = io.StringIO()
        with patch('builtins.input', return_value='operator'), patch('getpass.getpass',
                side_effect=['short', secret, 'does-not-match', secret, secret]), contextlib.redirect_stdout(output):
            initialize_admin(self.path)
        self.assertTrue(verify_password(secret, credentials(self.path)['password_hash']))
        self.assertIn('PASSWORD_LENGTH_REQUIRED', output.getvalue())
        self.assertIn('PASSWORD_CONFIRMATION_MISMATCH', output.getvalue())
        self.assertNotIn(secret, output.getvalue())
        self.assertNotIn(secret, self.path.read_text())
        self.assertEqual(list(self.env.glob('.panel-admin-*.tmp')), [])

    def test_exhausted_validation_never_creates_a_file(self):
        with patch('builtins.input', return_value='operator'), patch('getpass.getpass', return_value='short'), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ManualTestGuardError, 'PASSWORD_SETUP_ATTEMPTS_EXHAUSTED'):
                initialize_admin(self.path)
        self.assertFalse(self.path.exists())

    def test_hash_failure_never_leaves_empty_credentials(self):
        with patch('builtins.input', return_value='operator'), patch('getpass.getpass', return_value='synthetic-password'), \
                patch('security.hash_password', side_effect=RuntimeError('internal failure')):
            with self.assertRaises(RuntimeError): initialize_admin(self.path)
        self.assertFalse(self.path.exists())

    def test_atomic_publish_preserves_a_racing_initializer(self):
        def competing(source, destination):
            destination.write_text('other initializer credential')
            raise FileExistsError()
        with patch('builtins.input', return_value='operator'), patch('getpass.getpass', return_value='synthetic-password'), \
                patch('admin_testing_launcher.os.link', side_effect=competing):
            with self.assertRaises(FileExistsError): initialize_admin(self.path)
        self.assertEqual(self.path.read_text(), 'other initializer credential')
        self.assertEqual(list(self.env.glob('.panel-admin-*.tmp')), [])

    def test_missing_credentials_start_has_precise_error_and_never_checks_database(self):
        with patch('manual_android_test.load_profile', return_value={}), patch('fyp_test.operator_engine') as db, \
                patch('admin_testing_launcher.backend_probe') as probe:
            code, output = self.invoke()
        self.assertEqual(code, 1)
        self.assertIn('stage=credentials; code=ADMIN_CREDENTIALS_MISSING', output)
        db.assert_not_called(); probe.assert_not_called()

    def test_check_only_checks_ready_environment_without_admin_then_reports_setup_required(self):
        engine = MagicMock()
        with patch('manual_android_test.load_profile', return_value={}), patch('manual_android_test.install_network_guard'), \
                patch('admin_testing_launcher.backend_probe', return_value={'classroom_wifi': True}) as probe, \
                patch('fyp_test.operator_engine', return_value=engine), patch('sqlalchemy.inspect') as inspector:
            inspector.return_value.get_table_names.return_value = ['classroom_ble_policies']
            code, output = self.invoke('--check-only')
        report = json.loads(output)
        self.assertEqual(code, 1)
        self.assertEqual(report['result'], 'SETUP_REQUIRED')
        self.assertEqual(report['backend_and_database'], 'PASS')
        self.assertEqual(report['admin_credentials'], 'MISSING')
        probe.assert_called_once_with(8002, environment=self.env)
        engine.dispose.assert_called_once()
        self.assertFalse(self.path.exists())

    def test_eof_and_permission_failures_report_stage_without_secret_details(self):
        for exc, expected in [(EOFError(), 'INTERACTIVE_INPUT_REQUIRED'),
                              (PermissionError('secret-path-and-password'), 'PRIVATE_FILE_ACCESS_DENIED')]:
            with self.subTest(expected=expected), patch('manual_android_test.load_profile', return_value={}), \
                    patch('admin_testing_launcher.initialize_admin', side_effect=exc), patch('fyp_test.operator_engine') as db:
                code, output = self.invoke('--init-admin')
            self.assertEqual(code, 1)
            self.assertIn('stage=admin_initialization', output)
            self.assertIn('code=' + expected, output)
            self.assertNotIn('secret-path-and-password', output)
            db.assert_not_called()

    def test_unsupported_hidden_input_is_rejected_without_echo_fallback(self):
        with patch('builtins.input', return_value='operator'), patch('getpass.getpass', side_effect=getpass.GetPassWarning()):
            with self.assertRaisesRegex(ManualTestGuardError, 'INTERACTIVE_SECRET_INPUT_REQUIRED'):
                initialize_admin(self.path)
        self.assertFalse(self.path.exists())

    def test_valid_credentials_start_uses_pinned_environment_and_loopback_listener(self):
        with patch('manual_android_test.load_profile', return_value={'timezone': 'Asia/Kuala_Lumpur'}), \
                patch('manual_android_test.install_network_guard'), \
                patch('admin_testing_launcher.credentials', return_value={'username': 'operator', 'password_hash': 'test-hash'}), \
                patch('admin_testing_launcher.backend_probe', return_value={'classroom_wifi': True}) as probe, \
                patch('fyp_test.operator_engine') as db, patch('admin_testing.create_panel'), patch('uvicorn.run') as run:
            code, output = self.invoke()
        self.assertEqual(code, 0)
        probe.assert_called_once_with(8002, environment=self.env)
        self.assertEqual(run.call_args.kwargs['host'], '127.0.0.1')
        self.assertEqual(run.call_args.kwargs['port'], 8003)
        self.assertFalse(run.call_args.kwargs['proxy_headers'])
        self.assertFalse(run.call_args.kwargs['access_log'])
        db.return_value.dispose.assert_called_once()


if __name__ == '__main__': unittest.main()
