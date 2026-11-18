"""Offline PID reuse, exact ownership and lifecycle-state regression checks."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import disposable_processes as process
from manual_android_test import ManualTestGuardError


@unittest.skipUnless(sys.platform=='win32','Windows disposable-process launcher')
class ProcessIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.env=Path(self.temp.name)
        self.exe='C:/Python/python.exe'
        self.args=[self.exe,'-B','C:/FYP/backend/manual_android_test.py','--profile','C:/FYP/Test/backend-profile.json']
        self.row=dict(ProcessId=123,ExecutablePath=self.exe,created_at='2026-11-06T01:00:00.1234560Z',
            CommandLine='C:/Python/python.exe -B C:/FYP/backend/manual_android_test.py --profile C:/FYP/Test/backend-profile.json')

    def verify(self,rows=None,owners=()):
        with patch.object(process,'query_process',side_effect=lambda pid:(rows or {123:self.row}).get(pid)),patch.object(process,'listener_pids',return_value=list(owners)):
            return process.verified_pid(self.env,'backend',self.args,[self.exe],8002)

    def test_forward_and_backward_slashes_are_equivalent(self):
        row={**self.row,'CommandLine':self.row['CommandLine'].replace('/','\\'),'ExecutablePath':self.exe.replace('/','\\')}
        self.assertTrue(process.matches(row,self.args,[self.exe]))

    def test_substring_in_unrelated_command_is_not_ownership(self):
        row={**self.row,'CommandLine':'C:/Python/python.exe -m uvicorn main:app --port 8000 --description C:/FYP/Test'}
        self.assertFalse(process.matches(row,self.args,[self.exe]))
        self.assertFalse(process.matches({**self.row,'ExecutablePath':'C:/Other/python.exe'},self.args,[self.exe]))

    def test_legacy_valid_pid_upgrades_to_birth_and_executable(self):
        process.save_state(self.env,{'backend':123});self.assertEqual(self.verify(),123)
        self.assertEqual(process.read_state(self.env)['backend'],process.record(self.row))

    def test_exited_pid_and_free_port_retire_stale_state(self):
        process.save_state(self.env,{'backend':999,'database':456})
        self.assertIsNone(self.verify());self.assertEqual(process.read_state(self.env),{'database':456})
        self.assertIn('PROCESS_EXITED',(self.env/'process-state-history.jsonl').read_text())

    def test_recycled_pid_pointing_to_port8000_process_is_never_controlled(self):
        process.save_state(self.env,{'backend':123})
        foreign={**self.row,'CommandLine':'C:/Python/python.exe -m uvicorn main:app --port 8000'}
        self.assertIsNone(self.verify(rows={123:foreign}))
        self.assertFalse((self.env/'backend.stop').exists())
        self.assertIn('PID_NO_LONGER_OWNED',(self.env/'process-state-history.jsonl').read_text())

    def test_foreign_owner_of_8002_still_fails_closed(self):
        process.save_state(self.env,{'backend':123});before=process.read_state(self.env)
        foreign={**self.row,'CommandLine':'C:/Python/python.exe -m uvicorn main:app --port 8002'}
        with self.assertRaises(ManualTestGuardError):self.verify(rows={123:foreign},owners=[123])
        self.assertEqual(process.read_state(self.env),before)

    def test_valid_stored_pid_does_not_hide_foreign_listener(self):
        process.save_state(self.env,{'backend':process.record(self.row)})
        foreign={**self.row,'ProcessId':777,'CommandLine':'C:/Python/python.exe -m other'}
        with self.assertRaises(ManualTestGuardError):self.verify(rows={123:self.row,777:foreign},owners=[777])

    def test_missing_state_can_adopt_exact_owned_listener(self):
        self.assertEqual(self.verify(owners=[123]),123)
        self.assertEqual(process.read_state(self.env)['backend'],process.record(self.row))

    def test_reused_pid_observer_detects_original_exit(self):
        with patch.object(process,'query_process',side_effect=[self.row,{**self.row,'created_at':'2026-11-06T02:00:00.1234560Z'}]):
            self.assertEqual(process.ObservedProcess(123).poll(),0)

    def test_parallel_cli_lock_is_rejected_and_released(self):
        with process.lifecycle_lock(self.env):
            with self.assertRaises(RuntimeError):
                with process.lifecycle_lock(self.env):self.fail('Concurrent lifecycle allowed')
        with process.lifecycle_lock(self.env):pass

    def test_inspection_failure_does_not_erase_identity(self):
        process.save_state(self.env,{'backend':123})
        with patch.object(process,'query_process',side_effect=RuntimeError('query failed')):
            with self.assertRaises(RuntimeError):process.verified_pid(self.env,'backend',self.args,[self.exe],8002)
        self.assertEqual(process.read_state(self.env),{'backend':123})

    def test_unreadable_live_identity_is_not_classified_as_stale(self):
        process.save_state(self.env,{'backend':123})
        with self.assertRaises(ManualTestGuardError):self.verify(rows={123:{**self.row,'CommandLine':None}})
        self.assertEqual(process.read_state(self.env),{'backend':123})


if __name__=='__main__':unittest.main()
