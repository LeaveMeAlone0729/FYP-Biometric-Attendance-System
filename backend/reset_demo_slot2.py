"""Explicit OFFLINE local-demo reset; never installed as an API or startup hook.

Archives exact FK descendants before deleting only a DEMO001 local-demo Slot 2.
Does not authorize enrollment/replacement or change any Keystore/template.
"""
import argparse
import base64
from datetime import date, datetime, time
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from sqlalchemy import MetaData, and_, delete, insert, select, text


class ResetBlocked(RuntimeError):
    pass


def require(ok, code):
    if not ok:
        raise ResetBlocked(code)


def encode(value):
    if isinstance(value, bytes):
        return {'binary_base64': base64.b64encode(value).decode()}
    if isinstance(value, (datetime, date, time)):
        return {'type': type(value).__name__, 'iso': value.isoformat()}
    raise TypeError(type(value).__name__)


def packed(value):
    return json.dumps(value, default=encode, sort_keys=True, separators=(',', ':')).encode()


def unpack(data):
    """Decode checkpoint values for OFFLINE restore rehearsal/review, not import."""
    def hook(value):
        if set(value) == {'binary_base64'}:
            return base64.b64decode(value['binary_base64'], validate=True)
        if set(value) == {'type', 'iso'} and value['type'] in ('datetime', 'date', 'time'):
            return {'datetime': datetime, 'date': date, 'time': time}[value['type']].fromisoformat(value['iso'])
        return value
    return json.loads(data, object_hook=hook)


def reset_transaction(connection, folder, fingerprint, now):
    """Caller MUST hold an explicit transaction and have authenticated the operator.

    Fail closed on unknown cross-student references or an attendance/account root.
    Reflect existing schema only; never creates/alters tables or disables FKs.
    """
    require(re.fullmatch('[0-9a-f]{64}', fingerprint) is not None, 'EXACT_KEY_FINGERPRINT_REQUIRED')
    require(folder.is_dir() and not any(folder.iterdir()), 'NEW_EMPTY_PRIVATE_CHECKPOINT_REQUIRED')
    metadata = MetaData()
    metadata.reflect(bind=connection)
    student_table = metadata.tables['students']
    # Match normal device-management student lock before touching the target.
    student = connection.execute(select(student_table).where(
        student_table.c.student_id == 'DEMO001').with_for_update()).mappings().one()
    device_table = metadata.tables['registered_devices']
    devices = [dict(r) for r in connection.execute(select(device_table).where(
        device_table.c.student_id == 'DEMO001').with_for_update()).mappings()]
    samsung = [r for r in devices if r['slot_number'] == 1 and r['status'] == 'ACTIVE']
    targets = [r for r in devices if r['slot_number'] == 2]
    require(len(samsung) == 1 and 'SM-A346E' in samsung[0]['device_model'], 'PROTECTED_SAMSUNG_SLOT1_REQUIRED')
    require(len(targets) == 1, 'EXACTLY_ONE_SLOT2_HISTORY_REQUIRED')
    target = targets[0]
    require(target['status'] == 'ACTIVE' and target['device_id'].startswith('local-demo-')
            and target['public_key_fingerprint'] == fingerprint
            and target['device_model'] == 'Xiaomi 2410CRP4CG', 'TARGET_NOT_APPROVED_DEMO_XIAOMI')

    protected = {}
    for name in ('students', 'attendance', 'device_enrollment_revisions', 'school_provisioned_accounts'):
        if name in metadata.tables:
            table = metadata.tables[name]
            protected[name] = [dict(r) for r in connection.execute(select(table)).mappings()]
    protected['registered_devices_except_target'] = [dict(r) for r in connection.execute(
        select(device_table).where(device_table.c.device_id != target['device_id'])).mappings()]

    selected = {'registered_devices': {target['device_id']: target}}
    # Follow FK children only. Never follow parents into students/face/session data.
    for _ in range(len(metadata.tables) + 1):
        added = False
        for table in metadata.sorted_tables:
            keys = list(table.primary_key.columns)
            for fk in table.foreign_keys:
                parent = selected.get(fk.column.table.name, {})
                if not parent:
                    continue
                values = {r[fk.column.name] for r in parent.values()}
                rows = connection.execute(select(table).where(fk.parent.in_(values)).with_for_update()).mappings()
                for result in rows:
                    row = dict(result)
                    require(table.name not in protected, 'PROTECTED_TABLE_DEPENDENCY_REQUIRES_REVIEW')
                    require(row.get('student_id', 'DEMO001') == 'DEMO001', 'CROSS_STUDENT_REFERENCE_REQUIRES_REVIEW')
                    require(bool(keys), 'DEPENDENT_TABLE_WITHOUT_PRIMARY_KEY')
                    key = tuple(row[c.name] for c in keys)
                    bucket = selected.setdefault(table.name, {})
                    if table.name == 'registered_devices':
                        key = row['device_id']
                    if key not in bucket:
                        bucket[key] = row
                        added = True
        if not added:
            break
    else:
        raise ResetBlocked('DEPENDENCY_CLOSURE_DID_NOT_CONVERGE')

    snapshot = dict(version=1, purpose='EXPLICIT_LOCAL_DEMO001_SLOT2_RESET',
        occurred_at=now, target=target, rows={name: list(rows.values()) for name, rows in selected.items()},
        protected_sha256={name: hashlib.sha256(packed(rows)).hexdigest() for name, rows in protected.items()},
        schema={name: [{'name': c.name, 'type': str(c.type), 'computed': c.computed is not None}
                       for c in metadata.tables[name].columns] for name in selected})
    data = packed(snapshot)
    backup = folder / 'affected-records.json'
    with backup.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    digest = hashlib.sha256(data).hexdigest()
    require(hashlib.sha256(backup.read_bytes()).hexdigest() == digest, 'BACKUP_VERIFICATION_FAILED')
    with (folder / 'manifest.json').open('x') as stream:
        json.dump(dict(file=backup.name, bytes=len(data), sha256=digest,
                       table_counts={k: len(v) for k, v in snapshot['rows'].items()}), stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())

    for table in reversed(metadata.sorted_tables):
        for row in selected.get(table.name, {}).values():
            result = connection.execute(delete(table).where(and_(
                *[c == row[c.name] for c in table.primary_key.columns])))
            require(result.rowcount == 1, 'TARGET_CHANGED_TRANSACTION_ROLLED_BACK')
    for name, before in protected.items():
        if name == 'registered_devices_except_target':
            after = [dict(r) for r in connection.execute(select(device_table).where(
                device_table.c.device_id != target['device_id'])).mappings()]
        else:
            after = [dict(r) for r in connection.execute(select(metadata.tables[name])).mappings()]
        require(packed(before) == packed(after), 'PROTECTED_RECORD_CHANGED_TRANSACTION_ROLLED_BACK')
    require(connection.execute(select(device_table).where(device_table.c.slot_number == 2,
            device_table.c.student_id == 'DEMO001')).first() is None, 'SLOT2_NOT_EMPTY')
    event = metadata.tables['device_registration_events']
    connection.execute(insert(event).values(student_id='DEMO001', device_id=target['device_id'],
        action='local_demo_reset', outcome='success', code='LOCAL_DEMO_SLOT2_RESET', occurred_at=now))
    return dict(result='LOCAL_DEMO_SLOT2_RESET_COMMITTED', backup=str(folder), backup_sha256=digest,
                archived_table_counts={k: len(v) for k, v in snapshot['rows'].items()},
                slot1_preserved=True, attendance_preserved=True, enrollment_evidence_preserved=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm', required=True)
    parser.add_argument('--fingerprint', required=True)
    parser.add_argument('--checkpoint', required=True, type=Path)
    args = parser.parse_args(argv)
    engine = None
    committed = False
    try:
        require(os.environ.get('FYP_ENABLE_DEMO_SLOT2_RESET') == 'ONCE'
                and args.confirm == 'RESET-DEMO001-SLOT2', 'EXPLICIT_LOCAL_RESET_NOT_ENABLED')
        import original_fyp
        import httpx
        from config import local_now
        value = original_fyp.settings()
        require(value.demo_mode, 'ORIGINAL_DEMO_PROFILE_REQUIRED')
        require(args.checkpoint.is_absolute() and not args.checkpoint.exists(), 'FRESH_ABSOLUTE_CHECKPOINT_REQUIRED')
        pinned = original_fyp.probe()
        key = (original_fyp.PRIVATE / 'local-demo-slot2.key').read_bytes()
        require(len(key) == 32, 'LOCAL_OPERATOR_CREDENTIAL_REQUIRED')
        with httpx.Client(timeout=4, trust_env=False) as client:
            response = client.get('http://127.0.0.1:8000/local-fyp/demo-slot2')
            require(response.status_code == 200 and response.json().get('credential_sha256') ==
                    hashlib.sha256(key).hexdigest(), 'LIVE_LOCAL_DEMO_PROFILE_REQUIRED')
        args.checkpoint.mkdir(parents=False)
        owner = subprocess.check_output(['whoami'], text=True).strip()
        subprocess.run(['icacls', str(args.checkpoint), '/inheritance:r', '/grant:r',
                        owner + ':(OI)(CI)F', 'SYSTEM:(OI)(CI)F'], check=True,
                       capture_output=True, timeout=10)
        engine = original_fyp.bounded_engine(value)
        with engine.begin() as connection:
            require(original_fyp.identity(connection, value) == pinned, 'DATABASE_IDENTITY_CHANGED')
            require(all(r[0] == 'InnoDB' for r in connection.execute(text(
                "SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'"))),
                'TRANSACTIONAL_APPLICATION_TABLES_REQUIRED')
            now = local_now(value)
            for sql in (
                "SELECT COUNT(*) FROM verification_challenges WHERE student_id='DEMO001' AND consumed=0 AND expires_at>:now",
                "SELECT COUNT(*) FROM device_biometric_sessions WHERE student_id='DEMO001' AND stage IN ('FACE','LIVENESS') AND expires_at>:now",
            ):
                require(connection.execute(text(sql), {'now': now}).scalar_one() == 0,
                        'ACTIVE_DEMO_SCAN_FINISH_OR_CANCEL_FIRST')
            result = reset_transaction(connection, args.checkpoint, args.fingerprint, now)
        committed = True
        (args.checkpoint / 'result.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(result))
        return 0
    except Exception as error:
        print(json.dumps(dict(result='RESET_COMMITTED_REPORT_WRITE_FAILED' if committed else 'RESET_NOT_COMPLETED', reason=str(error) if isinstance(error, ResetBlocked)
                              else type(error).__name__, no_automatic_retry=True)))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
