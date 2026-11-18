"""Explicit opt-in synthetic schemas on guarded port 3322; no production access."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import sys
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine,inspect,text
from sqlalchemy.engine import URL
from manual_android_test import load_profile,install_network_guard,require
from fyp_test import DEFAULT_ENV,operator_engine,change_policy
from models import Base
import test_network_verification as network
import test_fyp_test_workflow as workflow
import test_attendance_authorization as authorization
import test_account_bound_enrollment as account
from prepare_manual_android_test import stop,start


def snapshot(engine):
    result={}
    with engine.connect() as c:
        for table in sorted(inspect(c).get_table_names()):
            require(re.fullmatch(r'[A-Za-z0-9_]+',table),'UNEXPECTED_TABLE')
            rows=c.exec_driver_sql('SELECT * FROM `'+table+'`').mappings().all()
            encoded=sorted(json.dumps(dict(r),default=str,sort_keys=True,separators=(',',':')) for r in rows)
            result[table]={'count':len(rows),'sha256':hashlib.sha256(json.dumps(encoded).encode()).hexdigest()}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    install_network_guard();env=DEFAULT_ENV;p=load_profile(env/'backend-profile.json')
    control=operator_engine(env,p);baseline=snapshot(control)
    report={'result':'FAIL','port':3322,'production_accessed':False,'source_baseline':baseline,
        'network_sources':'Controlled ASGI peers; not physical campus proof','cases':[]}
    schemas=[];engines=[];began=time.monotonic()
    def fresh():
        name='fypnetwork_synthetic_'+secrets.token_hex(6);schemas.append(name)
        with control.begin() as c:c.exec_driver_sql('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4')
        engine=create_engine(control.url.set(database=name),hide_parameters=True,pool_pre_ping=True,
            isolation_level='READ COMMITTED',connect_args={'use_pure':True,'connection_timeout':3,'read_timeout':8,'write_timeout':8})
        engines.append(engine);Base.metadata.create_all(engine);engine.dispose();return engine
    class Result(unittest.TextTestResult):
        def addSuccess(self,t):super().addSuccess(t);report['cases'].append({'id':t.id(),'status':'PASS'})
        def addFailure(self,t,e):super().addFailure(t,e);report['cases'].append({'id':t.id(),'status':'FAIL'})
        def addError(self,t,e):super().addError(t,e);report['cases'].append({'id':t.id(),'status':'FAIL'})
    try:
        suite=unittest.TestSuite()
        for cls in (network.NetworkTests,workflow.SimpleNetworkWorkflowTests,authorization.AttendanceAuthorizationTests,account.AccountBoundTests):
            for name in unittest.defaultTestLoader.getTestCaseNames(cls):
                t=cls(name)
                if cls is authorization.AttendanceAuthorizationTests:t.engine_factory=fresh
                else:t.engine_override=fresh()
                if cls is account.AccountBoundTests:t.replacement_engine_override=fresh()
                suite.addTest(t)
        with (args.output/'mariadb-tests.log').open('w') as log:
            result=unittest.TextTestRunner(stream=log,verbosity=2,resultclass=Result,failfast=True).run(suite)
        require(result.wasSuccessful(),'MARIADB_SCENARIO_FAILED')
        durable=fresh()
        from sqlalchemy.orm import Session
        with Session(durable) as db,db.begin():change_policy(db,'set',cidr='192.0.2.0/24',actor='isolated-restart-test')
        durable_before=snapshot(durable)
        for engine in engines:engine.dispose()
        control.dispose()
        # Stop/start only the identity-checked disposable services; preserve data/key.
        stop(env);start(env)
        require(snapshot(durable)==durable_before,'SIMULATION_POLICY_RESTART_CHANGED')
        require(snapshot(control)==baseline,'MANUAL_ANDROID_SOURCE_ROWS_CHANGED')
        report.update(result='PASS',tests=result.testsRun,graceful_restarts=1,
            simulation_policy_persisted=True,all_source_table_hashes_unchanged=True)
        with control.connect() as c:
            checks=[]
            for table in baseline:
                row=c.exec_driver_sql('CHECK TABLE `'+table+'`').all()
                require(all(r[2]=='status' and r[3]=='OK' for r in row),'TABLE_HEALTH_FAILED');checks.append(table)
            report['checked_source_tables']=len(checks)
    except Exception as exc:
        report['failure_type']=type(exc).__name__
        # Exception details can contain SQL parameters: retain privately, never print.
        import traceback
        (env/'network-integration-private-failure.log').write_text(traceback.format_exc())
    finally:
        for engine in engines:engine.dispose()
        try:
            for name in schemas:
                require(re.fullmatch('fypnetwork_synthetic_[0-9a-f]{12}',name) is not None,'UNSAFE_CLEANUP_TARGET')
                with control.begin() as c:c.exec_driver_sql('DROP DATABASE `'+name+'`')
            report['synthetic_schemas_cleaned']=len(schemas)
        except Exception:report.update(result='FAIL',cleanup_failed=True)
        control.dispose();report['seconds']=round(time.monotonic()-began,1)
        (args.output/'REPORT.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('cases','source_baseline')},indent=2))
    return 0 if report['result']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
