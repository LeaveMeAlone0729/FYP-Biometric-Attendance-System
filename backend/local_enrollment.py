"""Operator-only partner Local FYP enrollment setup. Never institution verification.

Configuration and evidence stay in the existing private Local directory. No
HTTP trust writer, face reset, forced activation, or copied operator key.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import time
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Student
from modules.devices import local_demo
from modules.devices.biometric_models import DeviceBiometricSession
from modules.devices.management_models import EnrollmentRevision, SchoolProvisionedAccount
from modules.devices.models import RegisteredDevice

CONFIRM = 'LOCAL-FYP-UNVERIFIED'
PRIVATE_FILES = ('settings.json', 'identity.json', 'local-device-management.json', 'local-enrollment.key')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def write_private(path, data):
    temporary = path.with_name(path.name + '.' + secrets.token_hex(4) + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def json_bytes(value):
    return (json.dumps(value, indent=2, default=str, sort_keys=True) + '\n').encode()


def checkpoint(folder, purpose, values):
    parent = folder/'enrollment-checkpoints'
    parent.mkdir(exist_ok=True)
    destination = parent/(datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(4))
    destination.mkdir()
    hashes = {}
    for name, content in values.items():
        require(Path(name).name == name, 'Invalid checkpoint filename.')
        (destination/name).write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        require(hashlib.sha256((destination/name).read_bytes()).hexdigest() == digest, 'Checkpoint verification failed.')
        hashes[name] = digest
    (destination/'manifest.json').write_bytes(json_bytes(dict(purpose=purpose, sha256=hashes)))
    return destination


def configure_files(folder, current_identity):
    """Change only the explicit Local policy, after validating the old pin."""
    from local_fyp import validate_profile
    folder = Path(folder)
    originals = {name: (folder/name).read_bytes() if (folder/name).is_file() else None for name in PRIVATE_FILES}
    require(all(not (folder/name).is_symlink() for name in PRIVATE_FILES), 'Private configuration must not be linked elsewhere.')
    profile = validate_profile(json.loads(originals['settings.json'].decode('utf-8-sig')))
    require(json.loads(originals['identity.json'].decode('utf-8-sig')) == current_identity,
            'The current pinned database identity must match before changing enrollment policy.')
    require(profile['fyp_account_bound_enrollment'] == current_identity['account_bound_fyp'], 'Existing enrollment policy pin differs.')
    enabled = local_demo.account_profile(folder)
    key = originals['local-enrollment.key']
    require(key is None or len(key) == 32, 'Existing Local operator credential is invalid; it was not replaced.')
    require(not enabled or key is not None, 'Enabled Local policy is missing its original operator credential.')
    if enabled and profile['fyp_account_bound_enrollment']:
        return None
    backup = checkpoint(folder, 'ENABLE_LOCAL_FYP_ENROLLMENT', {name: value for name, value in originals.items() if value is not None})
    updated = dict(profile, fyp_account_bound_enrollment=True)
    pinned = dict(current_identity, account_bound_fyp=True)
    try:
        if key is None:
            write_private(folder/'local-enrollment.key', secrets.token_bytes(32))
        write_private(folder/'settings.json', json_bytes(updated))
        write_private(folder/'identity.json', json_bytes(pinned))
        write_private(folder/'local-device-management.json', json_bytes(dict(version=1, enabled=True)))
    except Exception:
        for name, content in originals.items():
            if content is None:
                (folder/name).unlink(missing_ok=True)
            else:
                write_private(folder/name, content)
        raise
    return backup


def provision_account(db, student, now):
    require(student is not None and student.account_status == 'active', 'An active student account is required.')
    existing = db.get(SchoolProvisionedAccount, student.student_id)
    if existing is not None:
        return False
    db.add(SchoolProvisionedAccount(student_id=student.student_id,
        provisioning_reference='LOCAL-FYP-OPERATOR:' + student.student_id + ':' + secrets.token_hex(8),
        provisioned_at=now))
    db.flush()
    return True


def verify_live(folder, pinned):
    key = (folder/'local-enrollment.key').read_bytes()
    require(len(key) == 32 and local_demo.account_profile(folder), 'Local enrollment setup is not enabled.')
    with httpx.Client(timeout=5, trust_env=False) as client:
        response = client.get('http://127.0.0.1:8000/local-fyp/enrollment-status')
        require(response.status_code == 200, 'Restart the Local backend with enrollment support first.')
        status = response.json()
    require(status.get('environment') == 'partner_local' and status.get('identity') == pinned['identity']
        and status.get('first_enrollment_enabled') is True and status.get('device_management_enabled') is True
        and status.get('credential_sha256') == hashlib.sha256(key).hexdigest(), 'Live Local enrollment profile does not match.')
    return key


def record_local_account(engine, folder, student_id, scan_id, now, key):
    from local_account_verification import record_account
    info = {local_demo.CREDENTIAL: key, local_demo.ACCOUNT_POLICY: True, 'fyp_account_bound_enrollment': True}
    with Session(engine, info=info) as db, db.begin():
        student = db.scalar(select(Student).where(Student.student_id == student_id).with_for_update())
        require(student is not None, 'Student account not found.')
        revisions = db.scalars(select(EnrollmentRevision).where(EnrollmentRevision.student_id == student_id)).all()
        devices = list(db.execute(select(RegisteredDevice.device_id, RegisteredDevice.slot_number,
            RegisteredDevice.status, RegisteredDevice.public_key_fingerprint).where(RegisteredDevice.student_id == student_id)))
        snapshot = dict(student=student_id, scan=scan_id,
            revisions=[{column.name: getattr(row, column.name) for column in EnrollmentRevision.__table__.columns} for row in revisions],
            devices=[list(row) for row in devices])
        backup = checkpoint(folder, 'LOCAL_FYP_ACCOUNT_SETUP', {'prior-enrollment.json': json_bytes(snapshot)})
        revision = record_account(db, student_id, scan_id, now)
        after = list(db.execute(select(RegisteredDevice.device_id, RegisteredDevice.slot_number,
            RegisteredDevice.status, RegisteredDevice.public_key_fingerprint).where(RegisteredDevice.student_id == student_id)))
        require(devices == after, 'Device registrations changed during setup; enrollment was rolled back.')
    return revision, backup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    enable = actions.add_parser('enable')
    enable.add_argument('--confirm', required=True, choices=[CONFIRM])
    provision = actions.add_parser('provision')
    who = provision.add_mutually_exclusive_group(required=True)
    who.add_argument('--student')
    who.add_argument('--unenrolled', action='store_true')
    provision.add_argument('--confirm', required=True, choices=[CONFIRM])
    record = actions.add_parser('record')
    record.add_argument('--student', required=True)
    scan = record.add_mutually_exclusive_group(required=True)
    scan.add_argument('--scan')
    scan.add_argument('--watch', action='store_true')
    record.add_argument('--timeout', type=int, default=600)
    record.add_argument('--confirm', required=True, choices=[CONFIRM])
    actions.add_parser('status')
    args = parser.parse_args(argv)
    engine = None
    try:
        import local_fyp
        from app_time import local_now
        folder = local_fyp.private()
        profile = local_fyp.load_profile()
        pinned = local_fyp.probe(profile=profile)
        value = local_fyp.settings(profile)
        engine = local_fyp.engine(value)
        if args.action == 'enable':
            with socket.socket() as connection:
                connection.settimeout(.5)
                require(connection.connect_ex(('127.0.0.1', 8000)) != 0, 'Stop the Local backend before enabling its enrollment policy.')
            with engine.connect() as connection:
                identity = local_fyp.database_identity(connection, value)
            backup = configure_files(folder, identity)
            local_fyp.probe()  # Verify the updated pin against the same database/key/account.
            print(json.dumps(dict(result='LOCAL_FYP_ENROLLMENT_ENABLED', backup=str(backup) if backup else None,
                                  restart_required=True, institution_verified=False)))
            return 0
        if args.action == 'status':
            print(json.dumps(dict(database=value.db_name, first_enrollment_enabled=value.fyp_account_bound_enrollment,
                local_account_setup_enabled=local_demo.account_profile(folder))))
            return 0
        require(value.fyp_account_bound_enrollment and local_demo.account_profile(folder), 'Enable the Local FYP enrollment policy first.')
        if args.action == 'provision':
            with Session(engine) as db, db.begin():
                query = select(Student).where(Student.account_status == 'active').order_by(Student.student_id).with_for_update()
                if args.student:
                    query = query.where(Student.student_id == args.student.strip().upper())
                else:
                    query = query.where((Student.face_encoding.is_(None)) | (Student.face_encoding == ''))
                students = db.scalars(query).all()
                require(bool(students), 'No matching active accounts were found.')
                count = sum(provision_account(db, student, local_now(value)) for student in students)
            print(json.dumps(dict(result='LOCAL_FYP_ACCOUNTS_PROVISIONED', added=count, matching=len(students), face_data_changed=False)))
            return 0
        key = verify_live(folder, pinned)
        student_id = args.student.strip().upper()
        scan_id = args.scan
        if args.watch:
            require(1 <= args.timeout <= 1800, 'Watch timeout must be between 1 and 1800 seconds.')
            started = local_now(value)
            deadline = time.monotonic() + args.timeout
            print('Waiting for one NEW completed setup scan for ' + student_id + '. Cancel the old pending request and prepare again.', flush=True)
            while time.monotonic() < deadline:
                with Session(engine) as db:
                    scan_id = db.scalar(select(DeviceBiometricSession.approval_id).where(
                        DeviceBiometricSession.student_id == student_id,
                        DeviceBiometricSession.created_at >= started,
                        DeviceBiometricSession.stage == 'COMPLETED_UNTRUSTED',
                        DeviceBiometricSession.expires_at > local_now(value),
                        DeviceBiometricSession.candidate_device_id.startswith(local_demo.PREFIX),
                    ).order_by(DeviceBiometricSession.created_at.desc()).limit(1))
                if scan_id:
                    break
                time.sleep(2)
            require(scan_id is not None, 'No fresh completed scan received. No enrollment record was changed.')
        revision, backup = record_local_account(engine, folder, student_id, scan_id, local_now(value), key)
        print(json.dumps(dict(result='LOCAL_FYP_ACCOUNT_RECORDED_UNVERIFIED', student=student_id,
            backup=str(backup), device_activated=False,
            next='Cancel the setup request. Prepare a NEW second-device request and complete another genuine scan.')))
        return 0
    except Exception as exc:
        from local_account_verification import AccountVerificationRejected
        reason = str(exc) if isinstance(exc, (ValueError, AccountVerificationRejected, local_fyp.LocalError)) else type(exc).__name__
        print(json.dumps(dict(result='LOCAL_ENROLLMENT_NOT_COMPLETED', reason=reason)))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
