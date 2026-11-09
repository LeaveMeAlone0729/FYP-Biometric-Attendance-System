"""Portable setup paths exercised without connecting to MariaDB/MySQL."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import setup as installer


class SetupTests(unittest.TestCase):
    def test_model_only_bypasses_database_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(installer, 'ROOT', root), \
                    patch.object(installer, 'install_hand_model', return_value=root / 'hand.task') as model, \
                    patch('mysql.connector.connect') as connect, \
                    patch.object(sys, 'argv', ['setup.py', '--model-only']), \
                    contextlib.redirect_stdout(io.StringIO()):
                installer.main()
            model.assert_called_once_with()
            connect.assert_not_called()
            self.assertFalse((root / '.env').exists())

    def test_fresh_demo_password_requires_interactive_matching_input(self):
        with patch.object(sys.stdin, 'isatty', return_value=False):
            with self.assertRaisesRegex(SystemExit, 'interactive terminal'):
                installer.new_demo_password()
        with patch.object(sys.stdin, 'isatty', return_value=True):
            with patch('getpass.getpass', side_effect=['synthetic-password', 'does-not-match']):
                with self.assertRaisesRegex(SystemExit, 'match its confirmation'):
                    installer.new_demo_password()
            with patch('getpass.getpass', side_effect=['synthetic-password'] * 2):
                self.assertEqual(installer.new_demo_password(), 'synthetic-password')
