"""Offline, pinned 3322-only migration: cold application writes, logical restore rehearsal.
No production defaults, no policy seeding, no changes to existing application rows.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import shutil
from sqlalchemy import create_engine, inspect, text
from fyp_test import DEFAULT_ENV, operator_engine, stop_backend
from manual_android_test import install_network_guard, load_profile, require
from disposable_processes import lifecycle_lock
from modules.classroom_wifi.migration import upgrade


def snapshot(engine, names):
    result = {}
    with engine.connect() as c:
        for table in sorted(names):
            require(re.fullmatch(r'[a-z_]+', table), 'UNSAFE_TABLE_NAME')
            rows = [json.dumps(list(row), default=lambda v: v.hex() if isinstance(v, bytes) else str(v),
                               ensure_ascii=True, separators=(',', ':'))
                    for row in c.exec_driver_sql('SELECT * FROM `' + table + '`')]
            result[table] = dict(rows=len(rows), sha256=hashlib.sha256('\n'.join(sorted(rows)).encode()).hexdigest())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New private backup directory OUTSIDE repository')
    parser.add_argument('--apply', required=True, action='store_true')
    parser.add_argument('--component',choices=('wifi','ble'),default='wifi')
    args = parser.parse_args()
    migrate=upgrade
    if args.component=='ble':
        from modules.classroom_ble.migration import upgrade as ble_upgrade
        migrate=ble_upgrade
    root = Path(__file__).resolve().parents[1]
    require(not args.output.resolve().is_relative_to(root), 'PRIVATE_BACKUP_OUTSIDE_REPOSITORY_REQUIRED')
    args.output.mkdir(parents=True, exist_ok=False)
    install_network_guard()
    p = load_profile(DEFAULT_ENV / 'backend-profile.json')
    report = dict(result='FAIL', port=3322, production_accessed=False, policies_seeded=False)
    engine = operator_engine(DEFAULT_ENV, p)
    rehearsal = None; restored = None
    try:
        with lifecycle_lock(DEFAULT_ENV):
            stop_backend(DEFAULT_ENV)  # Only verified owned backend; database remains available on 3322.
            for name in ('backend-profile.json','server.ini','operator.json'):
                shutil.copy2(DEFAULT_ENV/name,args.output/name)  # Private matching encryption/configuration evidence.
            names = inspect(engine).get_table_names()
            with engine.connect() as c:
                nontransactional = c.execute(text('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=:s AND ENGINE <> \'InnoDB\''), {'s':p['db_name']}).all()
                require(not nontransactional, 'INNODB_ONLY_BACKUP_REQUIRED')
            before = snapshot(engine, names)
            (args.output/'before.json').write_text(json.dumps(before, indent=2))
            secret = json.loads((DEFAULT_ENV/'operator.json').read_text())['admin_password']
            private_env = dict(os.environ, MYSQL_PWD=secret)
            # MariaDB 10.4 mysqldump lacks mysql.exe's --connect-timeout flag.
            # Both subprocesses have independent hard 60-second deadlines.
            common = ['--no-defaults','--protocol=TCP','--host=127.0.0.1','--port=3322','--user=fyp_manual_admin']
            dump = args.output/'disposable-before.sql'
            with dump.open('xb') as output:
                result = subprocess.run([str(DEFAULT_ENV/'runtime/bin/mysqldump.exe'), *common,
                    '--single-transaction','--skip-lock-tables','--hex-blob',p['db_name']],
                    env=private_env,stdout=output,stderr=subprocess.PIPE,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            require(result.returncode==0 and dump.stat().st_size>1000,'DISPOSABLE_DUMP_FAILED')
            (args.output/'manifest.json').write_text(json.dumps({
                name:hashlib.sha256((args.output/name).read_bytes()).hexdigest()
                for name in ('backend-profile.json','server.ini','operator.json','disposable-before.sql')},indent=2))
            sql = dump.read_bytes()
            require(not re.search(rb'(?im)^\s*(?:USE\s|CREATE\s+DATABASE\s)', sql),'CROSS_SCHEMA_DUMP_REJECTED')
            rehearsal = 'fypwifirehearsal_'+secrets.token_hex(6)
            with engine.begin() as c:c.exec_driver_sql('CREATE DATABASE `'+rehearsal+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci')
            with dump.open('rb') as source:
                result = subprocess.run([str(DEFAULT_ENV/'runtime/bin/mysql.exe'),*common,rehearsal],
                    env=private_env,stdin=source,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            require(result.returncode==0,'RESTORE_REHEARSAL_FAILED')
            restored=create_engine(engine.url.set(database=rehearsal),hide_parameters=True,
                connect_args={'use_pure':True,'connection_timeout':3,'read_timeout':8,'write_timeout':8})
            require(snapshot(restored,names)==before,'RESTORED_DATA_MISMATCH')
            tables=migrate(restored);migrate(restored)
            require(snapshot(restored,names)==before,'REHEARSAL_CHANGED_EXISTING_ROWS')
            with restored.connect() as c:
                checks=[c.exec_driver_sql('CHECK TABLE `'+name+'`').all() for name in inspect(restored).get_table_names()]
                require(all(row[3]=='OK' for group in checks for row in group if row[2]=='status'),'REHEARSAL_CHECK_FAILED')
            # Apply only after the logical backup restored, compared, migrated twice and checked.
            require(snapshot(engine,names)==before,'SOURCE_CHANGED_DURING_REHEARSAL')
            migrate(engine);migrate(engine)
            with engine.begin() as c:
                for name in tables:
                    if args.component=='ble':
                        if name=='classroom_ble_policy_events':continue  # Offline operator audit only.
                        verbs='SELECT' if name=='classroom_ble_policies' else 'SELECT, INSERT, UPDATE' if name=='classroom_ble_challenges' else 'INSERT'
                        c.exec_driver_sql('GRANT '+verbs+' ON `'+p['db_name']+'`.`'+name+"` TO 'fyp_manual_runtime'@'127.0.0.1'")
                        continue
                    verbs = ('SELECT, INSERT, UPDATE' if name in ('classroom_wifi_challenges','attendance_wifi_bindings') else
                             'SELECT, INSERT' if name=='attempt_classroom_requirements' else
                             'SELECT' if name=='session_classroom_requirements' else
                             'SELECT' if name in ('wifi_classrooms','classroom_wifi_policies') else 'INSERT')
                    c.exec_driver_sql('GRANT '+verbs+' ON `'+p['db_name']+'`.`'+name+"` TO 'fyp_manual_runtime'@'127.0.0.1'")
            after=snapshot(engine,names)
            require(before==after,'EXISTING_RECORDS_CHANGED')
            report.update(result='PASS', original_tables=len(names), additive_tables=tables,
                dump_sha256=hashlib.sha256(sql).hexdigest(), restore_comparison=True,
                resumable_migration=True, all_existing_rows_unchanged=True, table_checks=True,
                backend_left_stopped=True)
            (args.output/'after.json').write_text(json.dumps(after,indent=2))
    finally:
        if restored is not None:restored.dispose()
        if rehearsal is not None:
            require(re.fullmatch(r'fypwifirehearsal_[0-9a-f]{12}',rehearsal),'UNSAFE_REHEARSAL_CLEANUP')
            with engine.begin() as c:c.exec_driver_sql('DROP DATABASE `'+rehearsal+'`')
        engine.dispose()
        (args.output/'REPORT.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
