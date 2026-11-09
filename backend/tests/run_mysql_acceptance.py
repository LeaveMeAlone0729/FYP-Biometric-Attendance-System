"""Fresh synthetic schemas only on the identity-verified private MySQL instance."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import secrets
import sys
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import mysql_testing as target
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--suite',choices=('all','account','admin'),default='all')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    env,p=target.load();target.network_guard(p['db_port']);control=target.engine(env,p,'root')
    schemas=[];engines=[];started=time.monotonic();report=dict(result='FAIL',vendor='mysql',version=p['version'],port=p['db_port'],production_accessed=False,cases=[])
    def fresh():
        name='fypmysqlcase_'+secrets.token_hex(6);schemas.append(name)
        with control.begin() as c:c.exec_driver_sql('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci')
        e=target.engine(env,p,'root',schema=name);engines.append(e)
        # Fixture-only approval tables live in shared test metadata, never in the
        # 43-table production model inventory. Test setup may create them here.
        for table in target.all_tables():table.create(e,checkfirst=True)
        with control.begin() as c:target.grants(c,name)
        return e
    def runtime(f):
        pcase={**p,'db_name':f.sessions.kw['bind'].url.database}
        e=target.engine(env,pcase,'runtime');engines.append(e)
        context=f.fixture.app.state.context if hasattr(f,'fixture') else f.app.state.context
        context.engine=e;context.sessions=sessionmaker(bind=e,expire_on_commit=False)
        context.sessions.configure(info={'fyp_account_bound_enrollment':False})
    class Result(unittest.TextTestResult):
        def addSuccess(self,test):super().addSuccess(test);report['cases'].append(dict(id=test.id(),status='PASS'))
        def addFailure(self,test,err):super().addFailure(test,err);report['cases'].append(dict(id=test.id(),status='FAIL'))
        def addError(self,test,err):super().addError(test,err);report['cases'].append(dict(id=test.id(),status='FAIL'))
        def addSkip(self,test,reason):super().addSkip(test,reason);report['cases'].append(dict(id=test.id(),status='SKIP',reason=reason))
    try:
        from test_account_bound_enrollment import AccountBoundTests
        from test_network_verification import NetworkTests
        from test_attendance_authorization import AttendanceAuthorizationTests
        from test_classroom_wifi import ClassroomWifiTests
        from test_classroom_attendance import ClassroomAttendanceTests
        from test_classroom_ble import ClassroomBleTests
        from test_admin_testing import AdminPanelTests
        class MySQLOperatorPanelTests(AdminPanelTests):
            def setUp(self):
                super().setUp()
                from admin_testing import create_panel
                from fastapi.testclient import TestClient
                from manual_android_test import ManualTestGuardError
                role_engine=target.engine(env,{**p,'db_name':self.engine.url.database},'operator');engines.append(role_engine)
                def ready():
                    if not self.available:raise ManualTestGuardError('BACKEND_NOT_READY')
                    return self.capabilities
                self.app=create_panel(role_engine,username='operator',password_hash=self.password_hash,
                    ready=ready,now=lambda:self.f.now,clock=lambda:self.ticks,database_port=p['db_port'])
                self.client=TestClient(self.app,base_url='http://127.0.0.1:8003',client=('127.0.0.1',4567),follow_redirects=False)
                self.addCleanup(self.client.close)
        def restricted(cls):
            class RuntimeActorTests(cls):
                def setUp(self):
                    super().setUp()
                    runtime(self.f)
            RuntimeActorTests.__name__='MySQLRuntime'+cls.__name__
            return RuntimeActorTests
        suite=unittest.TestSuite()
        classes=(AccountBoundTests,) if args.suite=='account' else (MySQLOperatorPanelTests,) if args.suite=='admin' else (AccountBoundTests,restricted(NetworkTests),restricted(AttendanceAuthorizationTests),restricted(ClassroomWifiTests),restricted(ClassroomAttendanceTests),restricted(ClassroomBleTests),MySQLOperatorPanelTests)
        for cls in classes:
            for name in unittest.defaultTestLoader.getTestCaseNames(cls):
                t=cls(name);t.engine_override=fresh()
                if issubclass(cls,AttendanceAuthorizationTests):
                    t.engine_factory=fresh  # Its subtests deliberately tear down/recreate the whole fixture.
                if cls is AccountBoundTests:
                    t.replacement_engine_override=fresh();t.configure_runtime=runtime
                suite.addTest(t)
        with (args.output/'tests.log').open('w') as stream:
            result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Result).run(suite)
        report.update(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped))
        target.require(result.wasSuccessful(),'MYSQL_ACCEPTANCE_SCENARIOS_FAILED')
        # Actual InnoDB replacement race using ACCOUNT_BOUND_FYP, never SQLite trust fixtures.
        import test_account_bound_enrollment as account
        import test_device_replacement as replacement
        import test_device_biometrics as biometric
        from security import hash_password
        h=replacement.ReplacementTests();h.password_hash=hash_password('test-password');h.engine_override=fresh();h.setUp()
        try:
            runtime(h.f);account.prepare_account(h.f);target.require(account.enroll(h.f).status_code==200,'MYSQL_RACE_ENROLLMENT_FAILED')
            pending=h.prepare(2)
            bio=biometric.DeviceBiometricTests();bio.f=h.f;bio.p=h.h.p;bio.pending=pending;bio.complete()
            ready=h.post('/activation-readiness',{}).json();ch=h.post('/activation-challenges',{'approval_id':ready['approval_id']}).json()
            body={'approval_id':ready['approval_id'],'challenge_id':ch['challenge_id'],'signature':h.h.signature(ch)}
            with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(lambda _:h.post('/activate',body).status_code,range(2)))
            target.require(sorted(codes)==[200,409],'MYSQL_CONCURRENT_ACTIVATION_NOT_SINGLE_USE')
            report['concurrent_replacement_statuses']=sorted(codes)
            after=h.rows();target.require(after[h.h.binding.replaced_device_id]['status']=='REVOKED','MYSQL_OLD_DEVICE_NOT_REVOKED')
            target.require(after[h.f.device_id]==h.before[h.f.device_id],'MYSQL_OTHER_SLOT_CHANGED')
        finally:h.tearDown()
        report['schema']=target.verify_schema(control)
        # Permission checks use the real narrowly scoped actors against an empty schema.
        for role in ('runtime','operator'):
            e=target.engine(env,p,role);engines.append(e)
            for statement in ('DELETE FROM students WHERE 1=0','CREATE TABLE forbidden (id INT)',
                    'CREATE DATABASE forbidden_fyp','SELECT * FROM mysql.user',
                    "UPDATE device_enrollment_revisions SET assurance_level='INSTITUTION_VERIFIED' WHERE 1=0"):
                with e.connect() as c:
                    try:c.exec_driver_sql(statement)
                    except Exception as exc:
                        target.require(getattr(getattr(exc,'orig',exc),'errno',None) in (1044,1142,1143,1227),'MYSQL_UNEXPECTED_PERMISSION_ERROR')
                        report.setdefault('permission_denials',0);report['permission_denials']+=1
                    else:raise RuntimeError('MYSQL_UNEXPECTED_OPERATOR_PRIVILEGE')
                    finally:c.rollback()
        report['result']='PASS'
    except Exception as exc:
        report['failure_type']=type(exc).__name__
        if type(exc) is RuntimeError:report['failure_code']=str(exc)
    finally:
        for e in engines:e.dispose()
        for name in schemas:
            target.require(__import__('re').fullmatch(r'fypmysqlcase_[0-9a-f]{12}',name),'UNSAFE_TEST_SCHEMA_CLEANUP')
            target.clean_case(control,name)
        control.dispose();report.update(schemas_cleaned=len(schemas),seconds=round(time.monotonic()-started,1))
        (args.output/'REPORT.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2));return 0 if report['result']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
