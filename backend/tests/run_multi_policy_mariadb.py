"""Opt-in multi-policy REST tests on fresh schemas at verified loopback 3322.
Does not restart services or change the live manual-test policy/student data.
"""
import argparse,json,re,secrets,sys,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from models import Base
from manual_android_test import install_network_guard,load_profile,require
from fyp_test import DEFAULT_ENV,operator_engine
from test_fyp_test_workflow import SimpleNetworkWorkflowTests


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--suite',choices=('network','sessions','classroom','classroom-attendance','ble','admin'),default='network')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    install_network_guard();p=load_profile(DEFAULT_ENV/'backend-profile.json');control=operator_engine(DEFAULT_ENV,p)
    if args.suite=='admin':
        from test_admin_testing import AdminPanelTests
        test_class=AdminPanelTests
    elif args.suite=='ble':
        from test_classroom_ble import ClassroomBleTests
        test_class=ClassroomBleTests
    elif args.suite=='classroom-attendance':
        from test_classroom_attendance import ClassroomAttendanceTests
        test_class=ClassroomAttendanceTests
    elif args.suite=='classroom':
        from test_classroom_wifi import ClassroomWifiTests
        test_class=ClassroomWifiTests
    elif args.suite=='sessions':
        from test_manual_sessions import ManualSessionTests
        test_class=ManualSessionTests
    else:test_class=SimpleNetworkWorkflowTests
    report={'result':'FAIL','suite':args.suite,'port':3322,'production_accessed':False,'source':'Isolated operator/ASGI fixtures, not physical attendance','cases':[]}
    names=[];engines=[];began=time.monotonic()
    class Result(unittest.TextTestResult):
        def addSuccess(self,test):super().addSuccess(test);report['cases'].append({'id':test.id(),'status':'PASS'})
        def addFailure(self,test,err):super().addFailure(test,err);report['cases'].append({'id':test.id(),'status':'FAIL'})
        def addError(self,test,err):super().addError(test,err);report['cases'].append({'id':test.id(),'status':'FAIL'})
    try:
        suite=unittest.TestSuite()
        for method in unittest.defaultTestLoader.getTestCaseNames(test_class):
            name='fypmulticidr_'+secrets.token_hex(6);names.append(name)
            with control.begin() as c:c.exec_driver_sql('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4')
            engine=create_engine(control.url.set(database=name),hide_parameters=True,isolation_level='READ COMMITTED',
                connect_args={'use_pure':True,'connection_timeout':3,'read_timeout':8,'write_timeout':8})
            engines.append(engine);Base.metadata.create_all(engine);engine.dispose()
            test=test_class(method);test.engine_override=engine;suite.addTest(test)
        with (args.output/'tests.log').open('w') as log:
            result=unittest.TextTestRunner(stream=log,verbosity=2,resultclass=Result).run(suite)
        report.update(result='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors))
    finally:
        for engine in engines:engine.dispose()
        for name in names:
            require(re.fullmatch(r'fypmulticidr_[0-9a-f]{12}',name),'UNSAFE_TEST_SCHEMA_CLEANUP')
            with control.begin() as c:c.exec_driver_sql('DROP DATABASE `'+name+'`')
        control.dispose();report['schemas_cleaned']=len(names);report['seconds']=round(time.monotonic()-began,1)
        (args.output/'REPORT.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))
    return 0 if report['result']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
