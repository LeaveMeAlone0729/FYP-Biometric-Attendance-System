"""Create/start/stop one private synthetic Android environment; no production access."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
from sqlalchemy import create_engine,text,inspect,select,func,MetaData,Boolean,Integer
from sqlalchemy.engine import URL
import mysql.connector
import disposable_processes as processes
from manual_android_test import DB_PORT,HTTP_PORT,BASE,validate_profile,load_profile,validate_native_config,require

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('C:/FYP/DB-Acceptance/20261104-003620/runtime')
PMA_SOURCE=Path('C:/laragon/etc/apps/phpMyAdmin')
PHP=Path('C:/laragon/bin/php/php-8.3.30-Win32-vs16-x64/php.exe')
PMA_PORT=8082
QUIET=subprocess.CREATE_NO_WINDOW


def audit(event,args):
    if event=='socket.connect' and isinstance(args[1],tuple):
        host,port=args[1][:2]
        if port==3306:raise PermissionError('PRODUCTION_DATABASE_PORT_BLOCKED')
        require(host in ('127.0.0.1','::1','localhost') and (port not in range(3307,3400) or port==DB_PORT),
            'NON_DISPOSABLE_NETWORK_ACCESS_BLOCKED')


def private_directory(path):
    path.mkdir(parents=True,exist_ok=False)
    owner=subprocess.check_output(['whoami'],text=True,creationflags=QUIET).strip()
    subprocess.run(['icacls',str(path),'/inheritance:r','/grant:r',owner+':(OI)(CI)F','SYSTEM:(OI)(CI)F'],
        check=True,capture_output=True,creationflags=QUIET)


def connect(env,database=None):
    a=json.loads((env/'operator.json').read_text())
    return mysql.connector.connect(host='127.0.0.1',port=DB_PORT,user='fyp_manual_admin',
        password=a['admin_password'],database=database,connection_timeout=3,read_timeout=8,
        write_timeout=8,use_pure=True,autocommit=True)


def query(env,sql,args=None,database=None):
    with connect(env,database) as db:
        with db.cursor() as c:
            c.execute(sql,args)
            return c.fetchall() if c.with_rows else []


def identity(env):
    p=json.loads((env/'backend-profile.json').read_text())
    row=query(env,'SELECT @@port,@@datadir,@@version')[0]
    require(row[0]==DB_PORT and Path(row[1]).resolve()==(env/'data').resolve()
        and row[2]=='10.4.27-MariaDB','WRONG_DISPOSABLE_DATABASE')
    return p


def launch(env,kind,args,log=True):
    output=open(env/(kind+'.log'),'ab') if log else subprocess.DEVNULL
    child_env={k:v for k,v in os.environ.items() if not k.startswith(
        ('DB_','MYSQL_','BIOMETRIC_','ATTENDANCE_','FYP_','CF_','CLOUDFLARE_','TUNNEL_'))
        and k not in ('DEMO_MODE','FACE_DISTANCE_THRESHOLD','SESSION_HOURS','CHALLENGE_SECONDS')}
    proc=subprocess.Popen(args,cwd=str(ROOT),stdin=subprocess.DEVNULL,stdout=output,stderr=output,
        creationflags=QUIET,env=child_env)
    if log:output.close()
    images=process_images(kind) or [args[0]]
    processes.register(env,kind,proc.pid,args,images)
    return proc


def wait_database(env,process):
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        require(process.poll() is None,'DISPOSABLE_DATABASE_EXITED')
        try:identity(env);return
        except mysql.connector.Error:time.sleep(.25)
    raise RuntimeError('DISPOSABLE_DATABASE_READINESS_TIMEOUT')


def wait_http(url,process,seconds=60):
    import httpx
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        require(process.poll() is None,'DISPOSABLE_HTTP_PROCESS_EXITED')
        try:
            response=httpx.get(url,timeout=2,trust_env=False)
            if response.status_code==200:return response
        except httpx.HTTPError:pass
        time.sleep(.25)
    raise RuntimeError('DISPOSABLE_HTTP_READINESS_TIMEOUT')


def process_command(env,kind):
    if kind=='database':return [str(env/'runtime/bin/mysqld.exe'),'--defaults-file='+str(env/'server.ini'),'--console']
    if kind=='backend':return [sys.executable,'-B',str(ROOT/'backend/manual_android_test.py'),'--profile',str(env/'backend-profile.json')]
    if kind=='phpmyadmin':return [str(PHP),'-d','display_errors=Off','-d','log_errors=Off',
        '-d','session.save_path='+str(env/'sessions'),'-d','session.cookie_httponly=1',
        '-d','session.cookie_samesite=Lax','-S','127.0.0.1:'+str(PMA_PORT),'-t',str(env/'phpmyadmin')]
    raise ValueError('Unknown disposable process role')


def process_images(kind):
    if kind=='backend':return [sys.executable,sys._base_executable,str(ROOT/'backend/venv/Scripts/python.exe')]
    return [PHP] if kind=='phpmyadmin' else []


def verified_pid(env,kind):
    command=process_command(env,kind)
    images=process_images(kind) or [command[0]]
    port={'backend':HTTP_PORT,'database':DB_PORT,'phpmyadmin':PMA_PORT}[kind]
    return processes.verified_pid(env,kind,command,images,port)


def stop(env):
    # Validate all roles before any control action. Never signal an unrelated PID.
    owned={kind:verified_pid(env,kind) for kind in ('backend','phpmyadmin','database')}
    if owned['backend']:
        observed=processes.ObservedProcess(owned['backend'])
        (env/'backend.stop').touch()
        deadline=time.monotonic()+25
        while observed.poll() is None:
            require(time.monotonic()<deadline,'BACKEND_GRACEFUL_STOP_TIMEOUT');time.sleep(.25)
        processes.forget(env,'backend',owned['backend'])
    pid=owned['phpmyadmin']
    if pid:
        observed=processes.ObservedProcess(pid)
        processes.terminate_php(env,pid)
        deadline=time.monotonic()+10
        while observed.poll() is None:
            require(time.monotonic()<deadline,'PHP_STOP_TIMEOUT');time.sleep(.25)
        processes.forget(env,'phpmyadmin',pid)
    if owned['database']:
        observed=processes.ObservedProcess(owned['database'])
        identity(env)
        try:query(env,'SHUTDOWN')
        except mysql.connector.Error:pass
        deadline=time.monotonic()+20
        while observed.poll() is None:
            require(time.monotonic()<deadline,'DATABASE_GRACEFUL_STOP_TIMEOUT');time.sleep(.25)
        processes.forget(env,'database',owned['database'])


def start(env):
    load_profile(env/'backend-profile.json')
    validate_native_config((env/'server.ini').read_text(),env)
    owned={kind:verified_pid(env,kind) for kind in ('database','backend','phpmyadmin')}
    proc=processes.ObservedProcess(owned['database']) if owned['database'] else launch(env,'database',process_command(env,'database'))
    wait_database(env,proc)
    flag=env/'backend.stop'
    if flag.exists():flag.unlink()
    proc=processes.ObservedProcess(owned['backend']) if owned['backend'] else launch(env,'backend',process_command(env,'backend'))
    wait_http('http://127.0.0.1:'+str(HTTP_PORT)+'/',proc,90)
    proc=processes.ObservedProcess(owned['phpmyadmin']) if owned['phpmyadmin'] else launch(env,'phpmyadmin',process_command(env,'phpmyadmin'),log=False)
    wait_http('http://127.0.0.1:'+str(PMA_PORT)+'/',proc,15)


def prepare():
    require(SOURCE.is_dir() and PMA_SOURCE.is_dir() and PHP.is_file(),'TEST_DEPENDENCIES_MISSING')
    for port in (DB_PORT,HTTP_PORT,PMA_PORT):
        with socket.socket() as probe:probe.bind(('127.0.0.1',port))
    env=BASE/('manual-android-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3))
    private_directory(env)
    a={k:secrets.token_urlsafe(36) for k in ('admin_password','runtime_password','viewer_password')}
    a['student_password']='FypTest-'+secrets.token_hex(4)+'!'+secrets.token_hex(2)
    (env/'operator.json').write_text(json.dumps(a,indent=2))
    report={'result':'FAIL','environment':str(env),'db_port':DB_PORT,'http_port':HTTP_PORT,
        'phpmyadmin_port':PMA_PORT,'production_accessed':False}
    try:
        shutil.copytree(SOURCE,env/'runtime')
        for name in ('tmp','export','sessions','pma-temp'): (env/name).mkdir()
        run=subprocess.run([str(env/'runtime/bin/mysql_install_db.exe'),'--datadir='+str(env/'data'),'--port='+str(DB_PORT)],
            stdin=subprocess.DEVNULL,capture_output=True,timeout=60,creationflags=QUIET)
        (env/'initializer.log').write_bytes(run.stdout+run.stderr)
        require(run.returncode==0,'DATABASE_INITIALIZATION_FAILED')
        bootstrap=env/'bootstrap.sql'
        bootstrap.write_text("CREATE USER 'fyp_manual_admin'@'127.0.0.1' IDENTIFIED BY '"+a['admin_password']+"';\n"
            "GRANT ALL PRIVILEGES ON *.* TO 'fyp_manual_admin'@'127.0.0.1' WITH GRANT OPTION;\n")
        config=(f'[mysqld]\nport={DB_PORT}\nbind-address=127.0.0.1\nbasedir={env.as_posix()}/runtime\n'
            f'datadir={env.as_posix()}/data\ntmpdir={env.as_posix()}/tmp\ninit-file={bootstrap.as_posix()}\n'
            f'pid-file={env.as_posix()}/server.pid\nsecure-file-priv={env.as_posix()}/export\n'
            'skip-slave-start\nskip-log-bin\nevent-scheduler=OFF\naria-recover-options=OFF\nmyisam-recover-options=OFF\n'
            'local-infile=0\ninnodb-buffer-pool-size=64M\ndefault-storage-engine=InnoDB\nmax-connections=30\n'
            'max-statement-time=8\ncharacter-set-server=utf8mb4\ncollation-server=utf8mb4_general_ci\n')
        (env/'server.ini').write_text(config)
        schema='fypdevicemgmt_restore_'+secrets.token_hex(6)
        from cryptography.fernet import Fernet
        p=dict(db_host='127.0.0.1',db_port=DB_PORT,db_name=schema,db_user='fyp_manual_runtime',
            db_password=a['runtime_password'],expected_datadir=str(env/'data'),biometric_key=Fernet.generate_key().decode(),
            timezone='Asia/Kuala_Lumpur',session_hours=8,challenge_seconds=90,face_threshold=0.45,
            demo_mode=False,fyp_account_bound_enrollment=True)
        validate_profile(p);(env/'backend-profile.json').write_text(json.dumps(p,indent=2))
        proc=launch(env,'database',[str(env/'runtime/bin/mysqld.exe'),'--defaults-file='+str(env/'server.ini'),'--console'])
        wait_database(env,proc)
        (env/'server.ini').write_text(config.replace('init-file='+bootstrap.as_posix()+'\n',''));bootstrap.unlink()
        for user,host in query(env,"SELECT User,Host FROM mysql.user WHERE User<>'fyp_manual_admin'"):
            query(env,'ALTER USER %s@%s ACCOUNT LOCK',(user,host))
        # Remove only fresh initializer generic test grants, never historical grants.
        defaults=query(env,'SELECT Host,Db,User FROM mysql.db')
        require(all(row[1] in ('test','test\\_%') and row[2]=='' for row in defaults),'UNEXPECTED_INITIALIZER_PRIVILEGES')
        query(env,"DELETE FROM mysql.db WHERE User='' AND Db IN (%s,%s)",('test','test\\_%'))
        require(not query(env,'SELECT Host,Db,User FROM mysql.db'),'GENERIC_INITIALIZER_GRANTS_REMAIN')
        query(env,'FLUSH PRIVILEGES')
        query(env,'CREATE DATABASE `'+schema+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci')
        query(env,"CREATE USER 'fyp_manual_runtime'@'127.0.0.1' IDENTIFIED BY %s",(a['runtime_password'],))
        query(env,"CREATE USER 'fyp_manual_viewer'@'127.0.0.1' IDENTIFIED BY %s",(a['viewer_password'],))
        # Import only application modules, never automated Fixture* model classes.
        from application_factory import create_app
        from models import Base,Programme,StudentGroup,Student
        from modules.devices.management_models import MANAGEMENT_TABLES,SchoolProvisionedAccount,EnrollmentRevision
        from modules.devices.models import RegisteredDevice
        from modules.devices.management_migration import upgrade_management_schema
        from modules.devices.pending_migration import verify_table
        from modules.devices.two_device_migration import verify_guards
        from production_guard import required_grants
        from security import hash_password,verify_password
        from database import make_sessions
        engine=create_engine(URL.create('mysql+mysqlconnector',host='127.0.0.1',port=DB_PORT,database=schema,
            username='fyp_manual_admin',password=a['admin_password']),hide_parameters=True,
            connect_args={'connection_timeout':3,'read_timeout':8,'write_timeout':8,'use_pure':True})
        try:
            require(len(Base.metadata.tables)==31,'UNEXPECTED_APPLICATION_MODEL_SET')
            management_names={t.name for t in MANAGEMENT_TABLES}
            Base.metadata.create_all(engine,tables=[t for t in Base.metadata.sorted_tables if t.name not in management_names])
            migration=upgrade_management_schema(engine)
            require(not upgrade_management_schema(engine)['created_tables'],'MIGRATION_NOT_IDEMPOTENT')
            with engine.connect() as c:
                verify_guards(c)
                expected=MetaData()
                for table in Base.metadata.sorted_tables:table.to_metadata(expected)
                from sqlalchemy.dialects.mysql import TINYINT
                for table in Base.metadata.sorted_tables:
                    actual={x['name']:x for x in inspect(c).get_columns(table.name)}
                    for column in table.columns:
                        if isinstance(column.type,Boolean):
                            found=actual[column.name]['type']
                            require(isinstance(found,TINYINT) and found.display_width==1,'WRONG_BOOLEAN_STORAGE')
                            expected.tables[table.name].c[column.name].type=Integer()
                    verify_table(c,expected.tables[table.name])
            sessions=make_sessions(engine)
            password_hash=hash_password(a['student_password']);require(verify_password(a['student_password'],password_hash),'PASSWORD_HASH_INVALID')
            from app_time import local_now
            from types import SimpleNamespace
            now=local_now(SimpleNamespace(timezone='Asia/Kuala_Lumpur'))
            with sessions.begin() as db:
                require(db.get(Student,'FYPTEST001') is None,'TEST_STUDENT_ALREADY_EXISTS')
                db.add(Programme(programme_code='FYPTEST',programme_name='Synthetic FYP Test Programme'));db.flush()
                db.add(StudentGroup(group_id=1,programme_code='FYPTEST',group_name='FYP-TEST',year_of_study=3,semester=1,academic_year=now.year));db.flush()
                db.add(Student(student_id='FYPTEST001',group_id=1,name='FYPTEST001 (Synthetic Student)',email='fyptest001@example.test',
                    password_hash=password_hash,face_encoding=None,biometric_status='not_registered',account_status='active',created_at=now));db.flush()
                db.add(SchoolProvisionedAccount(student_id='FYPTEST001',provisioning_reference='SYNTHETIC_FYP_MANUAL_ACCOUNT_ONLY',provisioned_at=now))
            grants=required_grants();grants['device_enrollment_revisions'].add(('INSERT',None))
            for table,permissions in grants.items():
                for verb,column in permissions:
                    query(env,'GRANT '+verb+(' (`'+column+'`)' if column else '')+' ON `'+schema+'`.`'+table+"` TO 'fyp_manual_runtime'@'127.0.0.1'")
            query(env,'GRANT SELECT ON `'+schema+"`.`students` TO 'fyp_manual_viewer'@'127.0.0.1'")
            for table in Base.metadata.tables:
                result=query(env,'CHECK TABLE `'+schema+'`.`'+table+'`')
                require(any(row[2]=='status' and row[3]=='OK' for row in result),'TABLE_INTEGRITY_FAILED')
            report.update(database=schema,tables=31,migration=migration,password_hash_verified=True,
                school_provisioned=True,face_encoding_present=False,biometric_status='not_registered',enrollment_revisions=0,registered_devices=0)
        finally:engine.dispose()
        shutil.copytree(PMA_SOURCE,env/'phpmyadmin',ignore=shutil.ignore_patterns('config.inc.php','config.user.inc.php','tmp','.git'))
        cfg=("<?php\n$cfg['blowfish_secret']='"+secrets.token_hex(16)+"';\n$i=1;\n"
            "$cfg['Servers'][$i]['auth_type']='cookie';\n$cfg['Servers'][$i]['host']='127.0.0.1';\n"
            f"$cfg['Servers'][$i]['port']='{DB_PORT}';\n$cfg['Servers'][$i]['verbose']='FYP disposable Android tests — 3322';\n"
            "$cfg['Servers'][$i]['AllowRoot']=false;\n$cfg['Servers'][$i]['AllowNoPassword']=false;\n"
            "$cfg['Servers'][$i]['only_db']=['"+schema+"'];\n$cfg['AllowArbitraryServer']=false;\n"
            "$cfg['TempDir']='"+(env/'pma-temp').as_posix()+"';\n$cfg['SendErrorReports']='never';\n$cfg['VersionCheck']=false;\n")
        (env/'phpmyadmin/config.inc.php').write_text(cfg,encoding='utf-8')
        (env/'USER_CREDENTIALS.txt').write_text('PRIVATE DISPOSABLE TEST ONLY — DO NOT COMMIT\n\n'
            'Flutter student ID: FYPTEST001\nTemporary student password: '+a['student_password']+'\n\n'
            f'phpMyAdmin: http://127.0.0.1:{PMA_PORT}/\nDB server: 127.0.0.1:{DB_PORT}\nDatabase: '+schema+'\n'
            'phpMyAdmin username: fyp_manual_viewer\nphpMyAdmin password: '+a['viewer_password']+'\n'
            'Viewer has SELECT on synthetic students only. Do not use root or production credentials.\n',encoding='utf-8')
        denied=0
        actors=[('fyp_manual_runtime',a['runtime_password'],[
            'SELECT * FROM mysql.global_priv','CREATE DATABASE fyp_forbidden_manual_probe',
            'CREATE TABLE forbidden_probe (id INT)','UPDATE students SET name=\'forged\'',
            'UPDATE school_provisioned_accounts SET provisioning_reference=\'forged\'',
            'UPDATE device_enrollment_revisions SET assurance_level=\'INSTITUTION_VERIFIED\'',
            'SELECT * FROM attendance_proposal_xampp.students']),
            ('fyp_manual_viewer',a['viewer_password'],[
            'UPDATE students SET name=\'forged\'','SELECT * FROM auth_sessions',
            'SELECT * FROM school_provisioned_accounts','SELECT * FROM mysql.global_priv'])]
        for user,password,statements in actors:
            with mysql.connector.connect(host='127.0.0.1',port=DB_PORT,user=user,password=password,
                    database=schema,connection_timeout=3,read_timeout=8,write_timeout=8,use_pure=True) as db:
                with db.cursor() as cursor:
                    cursor.execute('SELECT student_id FROM students');require(cursor.fetchall()==[('FYPTEST001',)],'ACTOR_CANNOT_READ_STUDENT')
                    for statement in statements:
                        try:cursor.execute(statement)
                        except mysql.connector.Error as exc:
                            require(exc.errno in (1044,1142,1143,1227),'UNEXPECTED_PRIVILEGE_ERROR');denied+=1;db.rollback()
                        else:db.rollback();raise RuntimeError('ACTOR_PRIVILEGES_TOO_BROAD')
        report['expected_privilege_denials']=denied
        start(env)
        import httpx
        with httpx.Client(base_url='http://127.0.0.1:'+str(HTTP_PORT),timeout=10,trust_env=False) as client:
            check=client.get('/manual-test/isolation');require(check.status_code==200 and check.json()['production_port_blocked'] is True,'LIVE_PROCESS_ISOLATION_FAILED')
            bad=client.post('/login',json={'student_id':'FYPTEST001','password':secrets.token_urlsafe(32)});require(bad.status_code==401,'BAD_PASSWORD_NOT_REJECTED')
            login=client.post('/login',json={'student_id':'FYPTEST001','password':a['student_password']});require(login.status_code==200,'SYNTHETIC_LOGIN_FAILED')
            headers={'Authorization':'Bearer '+login.json()['access_token']}
            require(client.get('/me',headers=headers).json()['student_id']=='FYPTEST001','PROFILE_MISMATCH')
            require(client.get('/api/v1/devices',headers=headers).json()['active_count']==0,'UNEXPECTED_DEVICE_BINDING')
            require(client.post('/logout',headers=headers).status_code==200,'LOGOUT_FAILED')
            require(client.get('/me',headers=headers).status_code==401,'LOGOUT_NOT_REVOKED')
        row=query(env,'SELECT student_id,face_encoding,biometric_status,consent_at FROM students',database=schema)
        require(row==[('FYPTEST001',None,'not_registered',None)],'FACE_OR_ACCOUNT_STATE_CHANGED')
        require(query(env,'SELECT COUNT(*) FROM device_enrollment_revisions',database=schema)[0][0]==0,'FAKE_ENROLLMENT_REVISION')
        require(query(env,'SELECT COUNT(*) FROM registered_devices',database=schema)[0][0]==0,'UNEXPECTED_REGISTERED_DEVICE')
        report.update(result='PASS',login_profile_logout='PASS',production_port_guard='PASS: IPv4/IPv6/localhost audit denial',
            phpmyadmin_url='http://127.0.0.1:'+str(PMA_PORT)+'/',backend_url='http://127.0.0.1:'+str(HTTP_PORT),services='RUNNING')
        return env,report
    except Exception:
        import traceback
        (env/'private-failure.log').write_text(traceback.format_exc())
        try:stop(env)
        except Exception:pass
        raise
    finally:
        (env/'REPORT.json').write_text(json.dumps(report,indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start',action='store_true');parser.add_argument('--stop',action='store_true');parser.add_argument('--environment',type=Path)
    args=parser.parse_args();sys.addaudithook(audit)
    try:
        if args.start or args.stop:
            require(args.start!=args.stop and args.environment is not None,'ONE_EXPLICIT_ACTION_REQUIRED')
            env=args.environment.resolve(strict=True)
            require(env.is_relative_to(BASE.resolve()) and env.name.startswith('manual-android-'),'PRIVATE_ENVIRONMENT_REQUIRED')
            with processes.lifecycle_lock(env):
                if args.stop:stop(env)
                else:
                    try:start(env)
                    except Exception:
                        try:stop(env)
                        except Exception:pass
                        raise
            print('DISPOSABLE_SERVICES_'+('STOPPED' if args.stop else 'STARTED'));return 0
        require(args.environment is None,'NO_TARGET_OVERRIDE_ALLOWED')
        env,report=prepare();print(json.dumps(report,indent=2));return 0
    except Exception as exc:
        print('DISPOSABLE_SETUP_REJECTED: '+type(exc).__name__+'; review private environment report, no production fallback')
        return 1


if __name__=='__main__':raise SystemExit(main())
