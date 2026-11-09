"""Explicit backup-gated CREATE-missing-only upgrade of the original FYP schema.

Never repairs mysql system tables or seeds accounts, enrollment trust or policies.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from sqlalchemy import event, inspect, text
from sqlalchemy.schema import CreateTable, CreateIndex

from application_schema import application_tables
from original_fyp import settings, bounded_engine, identity, validate_schema
from modules.devices.pending_migration import verify_table


def snapshot(connection, names):
    result = {}
    for name in sorted(names):
        if not re.fullmatch('[a-z_]+', name):
            raise RuntimeError('UNEXPECTED_TABLE_NAME')
        rows = connection.execute(text('SELECT * FROM `' + name + '`'))
        columns, hashes = list(rows.keys()), []
        for row in rows:
            values = [(type(v).__name__, v.hex() if isinstance(v, (bytes, bytearray))
                       else str(v) if v is not None else None) for v in row]
            hashes.append(hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest())
        result[name] = dict(columns=columns, count=len(hashes),
            rows_sha256=hashlib.sha256(''.join(sorted(hashes)).encode()).hexdigest())
    return result


def upgrade(backup, apply=False):
    backup = backup.resolve(strict=True)
    manifest = json.loads((backup / 'manifest.json').read_text())
    if (manifest.get('result'), manifest.get('database'), manifest.get('port')) != (
            'VERIFIED_LOGICAL_DUMP', 'attendance_proposal_xampp', 3306):
        raise RuntimeError('VERIFIED_ORIGINAL_BACKUP_REQUIRED')
    dump = (backup / 'attendance_proposal_xampp.sql').read_bytes()
    if hashlib.sha256(dump).hexdigest() != manifest['dump_sha256']:
        raise RuntimeError('LOGICAL_BACKUP_HASH_MISMATCH')
    value = settings()
    # Retain the matching existing key; never generate a new one for migration.
    archived = dict(line.split('=', 1) for line in (backup / 'matching-backend.env').read_text(
        encoding='utf-8-sig').splitlines() if '=' in line and not line.lstrip().startswith('#'))
    if archived.get('BIOMETRIC_KEY') != value.biometric_key:
        raise RuntimeError('EXISTING_ENCRYPTION_KEY_MISMATCH')
    engine = bounded_engine(value)
    created, report = [], {}
    try:
        with engine.connect() as connection:
            actual = identity(connection, value)
            if actual['version'] != manifest['version']:
                raise RuntimeError('BACKUP_SERVER_VERSION_MISMATCH')
            connection.execute(text('SET SESSION lock_wait_timeout=3'))
            if connection.scalar(text("SELECT GET_LOCK('fyp_original_additive_schema',3)")) != 1:
                raise RuntimeError('ORIGINAL_MIGRATION_BUSY')
            try:
                expected = application_tables()
                existing = set(inspect(connection).get_table_names())
                baseline = set(manifest['tables'])
                if not baseline <= existing or existing - {t.name for t in expected}:
                    raise RuntimeError('UNEXPECTED_ORIGINAL_TABLE_INVENTORY')
                before = snapshot(connection, baseline)
                if before != manifest['tables']:
                    raise RuntimeError('ORIGINAL_RECORDS_CHANGED_SINCE_BACKUP')
                for table in expected:
                    if table.name in existing:
                        verify_table(connection, table)
                missing = [table for table in expected if table.name not in existing]
                report = dict(result='PLAN', missing_tables=[t.name for t in missing],
                    backup=str(backup), existing_rows_unchanged=True,
                    existing_table_alterations=0, existing_record_updates=0)
                # Compile complete DDL before touching the schema.
                for table in missing:
                    for ddl in [CreateTable(table)] + [CreateIndex(i) for i in table.indexes]:
                        sql = str(ddl.compile(dialect=engine.dialect)).lstrip().upper()
                        if not sql.startswith(('CREATE TABLE ', 'CREATE INDEX ', 'CREATE UNIQUE INDEX ')):
                            raise RuntimeError('NON_ADDITIVE_DDL_REJECTED')
                if apply:
                    allowed = {t.name for t in missing}
                    def guard(conn, cursor, statement, parameters, context, many):
                        statement = statement.lstrip()
                        if statement.upper().startswith(('SELECT ', 'SHOW ', 'DESCRIBE ')):
                            return
                        match = re.match(r'CREATE TABLE\s+`?([a-z_]+)`?\s*\(', statement, re.I)
                        index = re.match(r'CREATE (?:UNIQUE )?INDEX .+? ON\s+`?([a-z_]+)`?\s*\(', statement, re.I)
                        if (match or index) and (match or index).group(1) in allowed:
                            return
                        raise RuntimeError('NON_ADDITIVE_DATABASE_STATEMENT_REJECTED')
                    event.listen(connection, 'before_cursor_execute', guard)
                    try:
                        for table in missing:
                            table.create(connection, checkfirst=False)
                            connection.commit()  # DDL is nontransactional; validate each resumable step.
                            verify_table(connection, table)
                            created.append(table.name)
                            (backup.parent / (backup.name + '-migration-progress.json')).write_text(
                                json.dumps(dict(created_tables=created), indent=2))
                        validate_schema(connection)
                        if snapshot(connection, baseline) != before:
                            raise RuntimeError('ORIGINAL_RECORD_COMPARISON_FAILED_STOP_NO_ROLLBACK')
                        report.update(result='APPLIED', created_tables=created,
                                      total_tables=len(inspect(connection).get_table_names()))
                    finally:
                        event.remove(connection, 'before_cursor_execute', guard)
                return report
            finally:
                connection.rollback()
                connection.execute(text("SELECT RELEASE_LOCK('fyp_original_additive_schema')"))
                connection.commit()
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        result = upgrade(args.backup, args.apply)
        Path(__file__).resolve().parents[1].joinpath('.work/original-schema-upgrade-result.json').write_text(
            json.dumps(result, indent=2))
        print(json.dumps(result))
        return 0
    except Exception as exc:
        # Do not dump SQL parameters, credentials or original records.
        print(json.dumps(dict(result='BLOCKED', code=str(exc) if isinstance(exc, RuntimeError)
            else 'DATABASE_SCHEMA_OPERATION_FAILED', error_type=type(exc).__name__)))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
