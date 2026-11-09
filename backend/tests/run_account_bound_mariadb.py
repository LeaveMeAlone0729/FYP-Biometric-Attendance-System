"""Windows disposable-only acceptance runner; never connects to port 3306.

Copies compatible binaries, initializes clean system tables, restores the verified
dump read-only into a new schema, and tests synthetic accounts in OTHER schemas.
No production backend, HTTP listener, trust seed or real record update.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from sqlalchemy import create_engine, text, inspect, select, func
from sqlalchemy.engine import URL
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mysql.connector
from database import make_sessions
from models import Base, Student, Attendance
from modules.devices.management_migration import upgrade_management_schema
from modules.devices.two_device_migration import verify_original_data
from modules.devices.management_models import EnrollmentRevision
from modules.devices.models import RegisteredDevice
from production_guard import required_grants
import test_account_bound_enrollment as account
import test_device_replacement as replacement
import test_device_biometrics as biometric
from security import hash_password

PORT = 3321
ROOT = Path('C:/FYP/DB-DeviceManagement')
SOURCE = Path('C:/FYP/DB-Acceptance/20261104-003620/runtime')
BACKUP = Path('C:/FYP/DB-Backups/20261103-134817')
QUIET = subprocess.CREATE_NO_WINDOW


def require(condition, code):
    if not condition: raise RuntimeError(code)


def main():
    began=time.monotonic()
    require(os.name == 'nt' and SOURCE.is_dir(), 'WINDOWS_COMPATIBLE_BINARIES_REQUIRED')
    # Block this process from connecting to ANY database endpoint but the new one.
    def audit(event, args):
        if event == 'socket.connect' and isinstance(args[1], tuple):
            # Windows asyncio implements its private socketpair over ephemeral
            # loopback TCP. Permit that, while denying all existing DB ports.
            require(args[1][0] in ('127.0.0.1','::1') and args[1][1] not in range(3306,3321),
                    'NON_DISPOSABLE_NETWORK_ACCESS_BLOCKED')
    sys.addaudithook(audit)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', PORT))  # No contact with any existing database.
    work = ROOT / ('account-bound-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3))
    work.mkdir(parents=True, exist_ok=False)
    identity = subprocess.check_output(['whoami'], creationflags=QUIET, text=True).strip()
    subprocess.run(['icacls', str(work), '/inheritance:r', '/grant:r', identity+':(OI)(CI)F', 'SYSTEM:(OI)(CI)F'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, creationflags=QUIET)
    report = {'result': 'FAIL', 'port': PORT, 'location': str(work), 'production_accessed': False}
    server = None
    engines = []
    admin_password = secrets.token_urlsafe(36)
    app_password = secrets.token_urlsafe(36)
    def connect(database=None):
        return mysql.connector.connect(host='127.0.0.1', port=PORT, user='fyp_disposable_admin',
            password=admin_password, database=database, connection_timeout=3,
            read_timeout=8, write_timeout=8, use_pure=True, autocommit=True)
    def sql(statement, args=None, database=None):
        with connect(database) as db:
            with db.cursor() as c:
                c.execute(statement, args)
                return c.fetchall() if c.with_rows else []
    def engine(schema, runtime=False):
        result = create_engine(URL.create('mysql+mysqlconnector', host='127.0.0.1', port=PORT,
            username='fyp_account_runtime' if runtime else 'fyp_disposable_admin',
            password=app_password if runtime else admin_password, database=schema),
            hide_parameters=True, isolation_level='READ COMMITTED', pool_pre_ping=True,
            connect_args={'connection_timeout':3,'read_timeout':8,'write_timeout':8,'use_pure':True})
        engines.append(result)
        return result
    def start():
        nonlocal server
        log = open(work/'console.log', 'ab')
        server = subprocess.Popen([str(work/'runtime/bin/mysqld.exe'), '--defaults-file='+str(work/'server.ini'), '--console'],
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=QUIET)
        log.close()
        deadline = time.monotonic()+30
        while time.monotonic()<deadline:
            require(server.poll() is None, 'DISPOSABLE_SERVER_EXITED')
            try:
                row=sql('SELECT @@port,@@datadir,@@version')[0]
                require(row[0]==PORT and Path(row[1]).resolve()==(work/'data').resolve()
                    and row[2]=='10.4.27-MariaDB', 'WRONG_DISPOSABLE_SERVER')
                return
            except mysql.connector.Error:time.sleep(.25)
        raise RuntimeError('DISPOSABLE_READINESS_TIMEOUT')
    def stop():
        if server is not None and server.poll() is None:
            try:sql('SHUTDOWN')
            except mysql.connector.Error:pass
            server.wait(timeout=20)
    def health():
        tables=sql("SELECT TABLE_SCHEMA,TABLE_NAME FROM information_schema.TABLES WHERE TABLE_TYPE='BASE TABLE' AND TABLE_SCHEMA NOT IN ('information_schema','performance_schema')")
        for schema,table in tables:
            rows=sql('CHECK TABLE `'+schema+'`.`'+table+'`')
            require(any(r[2]=='status' and r[3]=='OK' for r in rows), 'TABLE_INTEGRITY_FAILED')
        return len(tables)
    def schema():
        name='fypaccount_synthetic_'+secrets.token_hex(6)
        sql('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci')
        e=engine(name);Base.metadata.create_all(e)
        grants=required_grants()
        # FYP demo actor: only first-enrollment INSERT, never UPDATE/DELETE trust.
        grants['device_enrollment_revisions'].add(('INSERT',None))
        for table,permissions in grants.items():
            for verb,column in permissions:
                target=verb+(' (`'+column+'`)' if column else '')
                sql('GRANT '+target+' ON `'+name+'`.`'+table+"` TO 'fyp_account_runtime'@'127.0.0.1'")
        return e
    def runtime(f):
        context=f.fixture.app.state.context
        current=engine(f.sessions.kw['bind'].url.database, True)
        context.engine=current;context.sessions=make_sessions(current)
        context.sessions.configure(info={'fyp_account_bound_enrollment':False})
    try:
        shutil.copytree(SOURCE, work/'runtime')
        for name in ('tmp','export'): (work/name).mkdir()
        run=subprocess.run([str(work/'runtime/bin/mysql_install_db.exe'), '--datadir='+str(work/'data'), '--port='+str(PORT)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, creationflags=QUIET)
        (work/'initializer.log').write_bytes(run.stdout+run.stderr)
        require(run.returncode==0,'INITIALIZER_FAILED')
        init=work/'bootstrap.sql'
        init.write_text("CREATE USER 'fyp_disposable_admin'@'127.0.0.1' IDENTIFIED BY '"+admin_password+"';\n"
            "GRANT ALL PRIVILEGES ON *.* TO 'fyp_disposable_admin'@'127.0.0.1' WITH GRANT OPTION;\n")
        config=(f'[mysqld]\nport={PORT}\nbind-address=127.0.0.1\nbasedir={work.as_posix()}/runtime\n'
            f'datadir={work.as_posix()}/data\ntmpdir={work.as_posix()}/tmp\n'
            f'init-file={init.as_posix()}\npid-file={work.as_posix()}/server.pid\n'
            'skip-slave-start\nskip-log-bin\nevent-scheduler=OFF\naria-recover-options=OFF\n'
            'myisam-recover-options=OFF\nlocal-infile=0\ninnodb-buffer-pool-size=64M\n'
            'max-connections=30\nmax-statement-time=8\ncharacter-set-server=utf8mb4\ncollation-server=utf8mb4_general_ci\n'
            f'secure-file-priv={work.as_posix()}/export\n')
        (work/'server.ini').write_text(config)
        start()
        # Remove bootstrap from future restarts; retain no default login accounts.
        (work/'server.ini').write_text(config.replace('init-file='+init.as_posix()+'\n',''))
        init.unlink()
        for user,host in sql("SELECT User,Host FROM mysql.user WHERE User <> 'fyp_disposable_admin'"):
            sql('ALTER USER %s@%s ACCOUNT LOCK',(user,host))
        sql("CREATE USER 'fyp_account_runtime'@'127.0.0.1' IDENTIFIED BY %s",(app_password,))
        dump=BACKUP/'attendance_proposal_xampp.sql'
        metadata=json.loads((BACKUP/'artifact-checksums.json').read_text())
        # Baseline SQL hash is preserved in a separate existing checksum manifest.
        digest=hashlib.sha256(dump.read_bytes()).hexdigest()
        require(digest in json.dumps(metadata), 'BACKUP_DUMP_HASH_MISMATCH')
        restored='fypdevicemgmt_restore_'+secrets.token_hex(6)
        sql('CREATE DATABASE `'+restored+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci')
        client=work/'client.ini'
        client.write_text('[client]\nuser=fyp_disposable_admin\npassword='+admin_password+f'\nhost=127.0.0.1\nport={PORT}\nprotocol=tcp\n')
        with dump.open('rb') as stream:
            run=subprocess.run([str(work/'runtime/bin/mysql.exe'),'--defaults-extra-file='+str(client),restored],
                stdin=stream,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=40,creationflags=QUIET)
        require(run.returncode==0,'RESTORE_FAILED')
        restored_engine=engine(restored)
        baseline=json.loads((BACKUP/'production-after-logical.json').read_text())
        require(len(baseline)==26,'EXPECTED_26_TABLE_BASELINE')
        verify_original_data(restored_engine,baseline)
        report['migration']=upgrade_management_schema(restored_engine)
        require(not upgrade_management_schema(restored_engine)['created_tables'],'MIGRATION_NOT_RESUMABLE')
        verify_original_data(restored_engine,baseline)
        report['restored_table_hashes_matched']=26
        report['restored_attendance_records']=sql('SELECT COUNT(*) FROM attendance',database=restored)[0][0]
        # Every scenario gets its own fresh synthetic schema, no writes to restore.
        account.AccountBoundTests.setUpClass()
        suite=unittest.TestSuite()
        for name in unittest.defaultTestLoader.getTestCaseNames(account.AccountBoundTests):
            test=account.AccountBoundTests(name);test.engine_override=schema()
            test.replacement_engine_override=schema();test.configure_runtime=runtime;suite.addTest(test)
        with (work/'tests.log').open('w') as output:
            result=unittest.TextTestRunner(stream=output,verbosity=2,failfast=True).run(suite)
        report['account_scenarios']={'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)}
        require(result.wasSuccessful(),'ACCOUNT_SCENARIO_FAILED')
        # Serialize two genuine first enrollments for the same precreated account.
        probe=account.AccountBoundTests('test_first_enrollment_login_and_immutable_id')
        probe.engine_override=schema();probe.configure_runtime=runtime;probe.setUp()
        try:
            account.prepare_account(probe.f)
            with ThreadPoolExecutor(max_workers=2) as pool:
                enrollment_codes=list(pool.map(lambda _:account.enroll(probe.f).status_code,range(2)))
            require(sorted(enrollment_codes)==[200,409],'CONCURRENT_ENROLLMENT_OVERWROTE_TEMPLATE')
            with probe.f.sessions() as db:
                require(db.scalar(select(func.count()).select_from(EnrollmentRevision))==1,'DUPLICATE_ENROLLMENT_REVISION')
            report['concurrent_enrollment_statuses']=sorted(enrollment_codes)
        finally:probe.doCleanups()
        # Competing confirmations use the real local provider and InnoDB locks.
        h=replacement.ReplacementTests();h.password_hash=hash_password('test-password');h.engine_override=schema();h.setUp()
        try:
            runtime(h.f);account.prepare_account(h.f);require(account.enroll(h.f).status_code==200,'RACE_ENROLLMENT_FAILED')
            # Distinct candidate requests cannot both own the same replacement.
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives import serialization
            other_key=ec.generate_private_key(ec.SECP256R1())
            other_public=base64.b64encode(other_key.public_key().public_bytes(
                serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
            with ThreadPoolExecutor(max_workers=2) as pool:
                attempts=list(pool.map(lambda p:h.begin(2,public_key_spki=p),[h.h.p.body['public_key_spki'],other_public]))
            require(sorted(r.status_code for r in attempts)==[201,409],'CONFLICTING_REPLACEMENTS_ACCEPTED')
            successful=next(r.json() for r in attempts if r.status_code==201)
            report['conflicting_replacement_statuses']=sorted(r.status_code for r in attempts)
            # Cancel the winning preparation, then use the fixture's retained key
            # for the independent activation race below. Never revoke a device.
            h.h.identifier=successful['pending_registration_id']
            require(h.post('/cancel',{}).status_code==200,'CANCEL_RACE_PREPARATION_FAILED')
            pending=h.prepare(2)
            bio=biometric.DeviceBiometricTests();bio.f=h.f;bio.p=h.h.p;bio.pending=pending;bio.complete()
            ready=h.post('/activation-readiness',{}).json()
            ch=h.post('/activation-challenges',{'approval_id':ready['approval_id']}).json()
            body={'approval_id':ready['approval_id'],'challenge_id':ch['challenge_id'],'signature':h.h.signature(ch)}
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes=list(pool.map(lambda _:h.post('/activate',body).status_code,range(2)))
            require(sorted(outcomes)==[200,409],'CONCURRENT_REPLACEMENT_NOT_SINGLE_USE')
            rows=h.rows();require(rows[h.h.binding.replaced_device_id]['status']=='REVOKED','OLD_KEY_NOT_REVOKED')
            require(rows[h.f.device_id]==h.before[h.f.device_id],'UNAFFECTED_SLOT_CHANGED')
            require(h.h.count(Attendance)==0,'UNEXPECTED_ATTENDANCE')
            durable_schema=h.f.sessions.kw['bind'].url.database
            enrollment_baseline=sql('SELECT s.student_id,SHA2(s.face_encoding,256),r.revision_id,r.template_hash,r.assurance_level FROM students s JOIN device_enrollment_revisions r ON r.student_id=s.student_id',database=durable_schema)
            report['concurrent_replacement_statuses']=sorted(outcomes)
        finally:h.tearDown()
        denials=0
        with engine(durable_schema,True).connect() as c:
            for statement in ('DELETE FROM students', 'CREATE TABLE forbidden (id INT)',
                'SELECT * FROM mysql.global_priv','SELECT * FROM `'+restored+'`.students',
                "UPDATE school_provisioned_accounts SET provisioning_reference='forged'",
                "UPDATE device_enrollment_revisions SET assurance_level='INSTITUTION_VERIFIED'"):
                try:c.exec_driver_sql(statement)
                except Exception as exc:
                    require(getattr(getattr(exc,'orig',None),'errno',None) in (1044,1142,1143,1227),
                        'UNEXPECTED_PERMISSION_ERROR')
                    denials+=1;c.rollback()
                else:raise RuntimeError('RUNTIME_PERMISSION_TOO_BROAD')
        report['permission_denials']=denials
        for cycle in range(3):
            report['checked_tables']=health()
            verify_original_data(restored_engine,baseline)
            for e in engines:e.dispose()
            stop();start()
            verify_original_data(restored_engine,baseline)
            require(sql("SELECT COUNT(*) FROM registered_devices WHERE status='ACTIVE'",database=durable_schema)[0][0]==2,'DEVICE_DURABILITY_FAILED')
            require(sql("SELECT COUNT(*) FROM device_biometric_authorizations WHERE consumed_at IS NOT NULL",database=durable_schema)[0][0]==1,'GRANT_DURABILITY_FAILED')
            require(sql('SELECT COUNT(*) FROM attendance',database=durable_schema)[0][0]==0,'ATTENDANCE_DURABILITY_FAILED')
            require(sql('SELECT s.student_id,SHA2(s.face_encoding,256),r.revision_id,r.template_hash,r.assurance_level FROM students s JOIN device_enrollment_revisions r ON r.student_id=s.student_id',database=durable_schema)==enrollment_baseline,'ENROLLMENT_REVISION_DURABILITY_FAILED')
        report['graceful_restarts']=3
        report['final_checked_tables']=health()
        verify_original_data(restored_engine,baseline)
        import re
        require(not re.search(r'corrupt|access violation|assertion failure|crash recovery',
            (work/'console.log').read_text(errors='replace'),re.I),'SERVER_LOG_HEALTH_FAILED')
        report['server_log_health']='PASS'
        report['account_bound_template_revision_durable']=True
        report['result']='PASS'
    except Exception as exc:
        # Exception text may contain driver parameters. Keep it only in private logs.
        import traceback
        (work/'private-failure.log').write_text(traceback.format_exc())
        report['failure_type']=type(exc).__name__
    finally:
        for e in engines:e.dispose()
        try:stop();report['server_stopped']=server is None or server.poll() is not None
        except Exception:report['server_stopped']=False;report['result']='FAIL'
        report['duration_seconds']=round(time.monotonic()-began,1)
        (work/'REPORT.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
    return 0 if report['result']=='PASS' else 1


if __name__=='__main__':
    began=time.monotonic()
    raise SystemExit(main())
