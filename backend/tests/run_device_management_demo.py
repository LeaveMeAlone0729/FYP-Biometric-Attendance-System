"""Offline synthetic supervisor demonstration. No HTTP server or production DB.

Uses the actual built-in local provider and REST/signing/transaction workflow.
Only enrollment and biometric input are explicitly synthetic test fixtures.
No command accepts real identities, database credentials, trust flags or ports.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import unittest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = args.output or root/'.work/device-management-demo.json'
    output = output.resolve()
    if not output.is_relative_to((root/'.work').resolve()):
        parser.error('Evidence output must be inside the ignored project .work directory')
    sys.path[:0] = [str(root/'backend'), str(root/'backend/tests')]
    sys.dont_write_bytecode = True
    os.environ['ATTENDANCE_DEVICE_MYSQL_TESTS'] = '0'
    os.environ.pop('ATTENDANCE_API_URL', None)
    import mysql.connector
    def reject(*args, **kwargs):
        raise AssertionError('External database connections are forbidden in this offline demo')
    mysql.connector.connect = reject
    sys.addaudithook(lambda event, values: (_ for _ in ()).throw(AssertionError('Database network access forbidden'))
        if event == 'socket.connect' and isinstance(values[1], tuple) and values[1][1] in range(3306, 3320) else None)
    from test_device_management import ManagementTests
    names = ['test_slot2_full_flow_with_local_provider_and_independent_keys',
             'test_local_slot1_replacement_revokes_old_key_preserves_slot2',
             'test_local_slot2_replacement_revokes_old_key_preserves_slot1',
             'test_self_enrolled_face_does_not_get_provenance_or_authorization',
             'test_invalid_signature_consumes_activation_challenge',
             'test_face_deletion_and_reenrollment_stay_blocked']
    cases = [ManagementTests(name) for name in names]
    suite = unittest.TestSuite(cases)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    evidence = dict(result='PASS' if result.wasSuccessful() else 'FAIL',
        tests=result.testsRun, environment='OFFLINE SYNTHETIC IN-MEMORY DEMONSTRATION',
        real_identity_trust_proven=False, production_or_mobile_devices_accessed=False,
        provider='built-in LocalDeviceApprovalProvider, not a replacement provider mock',
        cases=[getattr(case, 'demo_evidence', dict(test=case._testMethodName)) for case in cases])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2)+'\n')
    print(json.dumps(evidence, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__': raise SystemExit(main())
