"""Explicit disposable MySQL setup/lifecycle. No .env targets or production fallback."""
import argparse
from contextlib import contextmanager
from datetime import datetime, time as daytime, timedelta
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
import threading
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BASE = Path.home() / 'FYP-MySQL-Testing'  # Stable in ordinary PowerShell and packaged terminals alike.
SUPPORTED = {'8.4.3'}
QUIET = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
ACTORS = {'root': 'root', 'runtime': 'fyp_mysql_runtime', 'operator': 'fyp_mysql_operator'}


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def save(path, value):
    tmp = path.with_suffix('.new')
    tmp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def validate_profile(p, env):
    require(set(p) == {'format', 'vendor', 'version', 'server_uuid', 'db_host', 'db_port', 'db_name',
        'backend_port', 'panel_port', 'expected_datadir', 'expected_basedir', 'biometric_key',
        'timezone', 'session_hours', 'challenge_seconds', 'face_threshold', 'demo_mode',
        'fyp_account_bound_enrollment'}, 'MYSQL_PROFILE_FIELDS_INVALID')
    require(p['format'] == 1 and p['vendor'] == 'mysql' and p['version'] in SUPPORTED, 'MYSQL_VENDOR_VERSION_REJECTED')
    require(p['db_host'] == '127.0.0.1' and re.fullmatch(r'fypmysqltest_[0-9a-f]{12}', p['db_name'] or ''), 'MYSQL_SCHEMA_HOST_REJECTED')
    ports = [p[k] for k in ('db_port', 'backend_port', 'panel_port')]
    require(all(type(n) is int and 1024 <= n <= 65535 and n not in (3306,3322,8000,8002,8003) for n in ports)
            and len(set(ports)) == 3, 'MYSQL_RESERVED_OR_INVALID_PORT')
    require(all(not 3306<=p[k]<3400 for k in ('backend_port','panel_port')),'MYSQL_HTTP_PORT_IN_DATABASE_RANGE')
    require(Path(p['expected_datadir']).resolve() == (env/'data').resolve()
            and Path(p['expected_basedir']).resolve() == (env/'runtime').resolve(), 'MYSQL_DIRECTORY_REJECTED')
    require(re.fullmatch(r'[0-9a-f-]{36}', p['server_uuid'] or ''), 'MYSQL_UUID_REQUIRED')
    require(p['demo_mode'] is False and p['fyp_account_bound_enrollment'] is True
        and p['timezone'] == 'Asia/Kuala_Lumpur' and p['session_hours'] == 8
        and p['challenge_seconds'] == 90 and p['face_threshold'] == .45, 'MYSQL_APPLICATION_POLICY_REJECTED')
    from cryptography.fernet import Fernet
    Fernet(p['biometric_key'].encode('ascii'))
    return p


def load(env=None):
    if env is None:
        pointer = json.loads((BASE/'current.json').read_text())
        env = Path(pointer['environment'])
    env = Path(env).resolve(strict=True)
    require(env.parent == BASE.resolve() and re.fullmatch(r'env-[0-9a-f]{12}', env.name), 'MYSQL_PRIVATE_ENVIRONMENT_REQUIRED')
    p = validate_profile(json.loads((env/'profile.json').read_text()), env)
    require((env/'server.ini').read_text()==server_config(env,p), 'MYSQL_NATIVE_CONFIG_CHANGED')
    return env, p


def server_config(env,p):
    env=Path(p['expected_datadir']).parent  # Preserve the validated spelling across Windows path virtualization.
    return (f'[mysqld]\nbasedir={p["expected_basedir"].replace(chr(92),"/")}\ndatadir={p["expected_datadir"].replace(chr(92),"/")}\n'
        f'port={p["db_port"]}\nbind-address=127.0.0.1\nmysqlx=OFF\nlocal-infile=0\nevent-scheduler=OFF\nskip-log-bin\n'
        'default-storage-engine=InnoDB\ncharacter-set-server=utf8mb4\ncollation-server=utf8mb4_general_ci\n'
        f'secure-file-priv={str(env/"export").replace(chr(92),"/")}\npid-file={str(env/"server.pid").replace(chr(92),"/")}\n')


def network_guard(port):
    require(type(port) is int and port != 3306 and 1024 <= port <= 65535, 'MYSQL_ENDPOINT_REJECTED')
    def audit(event, args):
        if event == 'socket.connect' and isinstance(args[1], tuple):
            host, target = args[1][:2]
            if target == 3306 or (3307 <= target < 3400 and target != port):
                raise PermissionError('OTHER_DATABASE_ENDPOINT_BLOCKED')
            if host not in ('127.0.0.1', '::1', 'localhost'):
                raise PermissionError('NON_LOOPBACK_OUTBOUND_BLOCKED')
    sys.addaudithook(audit)


def all_tables():
    import importlib
    from models import Base
    modules=[importlib.import_module('models')]
    for name in ('models','verification_models','pending_models','biometric_models','activation_models','management_models'):
        modules.append(importlib.import_module('modules.devices.'+name))
    modules += [importlib.import_module(name) for name in ('modules.authorization.models','modules.networks.models',
        'modules.classroom_wifi.models','modules.classroom_ble.models')]
    from modules.classroom_wifi.models import ClassroomBase
    from modules.classroom_ble.models import BleBase
    names={obj.__table__.name for module in modules for obj in vars(module).values()
        if isinstance(obj,type) and obj.__module__==module.__name__ and hasattr(obj,'__table__')}
    return [t for m in (Base.metadata, ClassroomBase.metadata, BleBase.metadata) for t in m.sorted_tables if t.name in names]


def identity(c, p, role, schema=None):
    from sqlalchemy import text
    row = c.execute(text('SELECT VERSION(),@@version_comment,@@port,DATABASE(),CURRENT_USER(),@@datadir,@@basedir,@@server_uuid')).one()
    require(row[0] == p['version'] and 'mysql' in row[1].lower(), 'MYSQL_ACTUAL_VENDOR_VERSION_REJECTED')
    require((row[2],row[3],row[7]) == (p['db_port'], schema or p['db_name'],p['server_uuid']), 'MYSQL_ACTUAL_ENDPOINT_SCHEMA_UUID_REJECTED')
    require(row[4] == ACTORS[role] + ('@localhost' if role == 'root' else '@127.0.0.1'), 'MYSQL_ACTUAL_ACCOUNT_REJECTED')
    require(Path(row[5]).resolve() == Path(p['expected_datadir']).resolve()
        and Path(row[6]).resolve() == Path(p['expected_basedir']).resolve(), 'MYSQL_ACTUAL_DIRECTORY_REJECTED')


def engine(env, p, role='runtime', schema=None):
    from sqlalchemy import create_engine, event
    from sqlalchemy.engine import URL
    require(role in ACTORS, 'MYSQL_ROLE_REJECTED')
    target = schema or p['db_name']
    require(target == p['db_name'] or (role == 'root' and re.fullmatch(r'fypmysqlcase_[0-9a-f]{12}', target or '')), 'MYSQL_SCHEMA_OVERRIDE_REJECTED')
    secret = json.loads((env/'secrets.json').read_text())[role]
    require(isinstance(secret,str) and len(secret) >= 32, 'MYSQL_PRIVATE_SECRET_INVALID')
    result = create_engine(URL.create('mysql+mysqlconnector',host='127.0.0.1',port=p['db_port'],
        username=ACTORS[role],password=secret,database=target),hide_parameters=True,pool_pre_ping=True,
        isolation_level='READ COMMITTED',connect_args={'use_pure':True,'connection_timeout':3,'read_timeout':8,'write_timeout':8})
    @event.listens_for(result,'do_connect')
    def pin(dialect,record,args,kw):
        require((kw.get('host'),kw.get('port'),kw.get('user'),kw.get('database'),kw.get('use_pure')) ==
            ('127.0.0.1',p['db_port'],ACTORS[role],target,True), 'MYSQL_CONNECTION_OVERRIDE_REJECTED')
    @event.listens_for(result,'connect')
    def verify(raw, record):
        # Validate every newly opened DBAPI connection before any application query.
        cursor=raw.cursor()
        try:
            cursor.execute('SELECT VERSION(),@@version_comment,@@port,DATABASE(),CURRENT_USER(),@@datadir,@@basedir,@@server_uuid')
            row=cursor.fetchone()
            require(row[0]==p['version'] and 'mysql' in row[1].lower() and row[2]==p['db_port']
                and row[3]==target and row[4]==ACTORS[role]+('@localhost' if role=='root' else '@127.0.0.1')
                and Path(row[5]).resolve()==Path(p['expected_datadir']).resolve()
                and Path(row[6]).resolve()==Path(p['expected_basedir']).resolve() and row[7]==p['server_uuid'],
                'MYSQL_NEW_CONNECTION_IDENTITY_REJECTED')
        finally:cursor.close()
    try:
        with result.connect() as c:identity(c,p,role,target)
    except Exception:
        result.dispose();raise
    return result


def verify_schema(e):
    from sqlalchemy import inspect, text
    from database_compat import normalized_expression, verify_check_enforcement
    tables=all_tables();counts=dict(tables=0,checks=0,foreign_keys=0,unique_guards=0,computed_columns=0)
    with e.connect() as c:
        i=inspect(c)
        actual=set(i.get_table_names());expected={t.name for t in tables}
        require(actual==expected, 'MYSQL_43_TABLE_SET_MISMATCH: missing='+','.join(sorted(expected-actual))+'; extra='+','.join(sorted(actual-expected)))
        verify_check_enforcement(c)
        for t in tables:
            cols={x['name']:x for x in i.get_columns(t.name)}
            require(set(cols)==set(t.c.keys()),'MYSQL_COLUMN_SET_MISMATCH:'+t.name)
            require(i.get_table_options(t.name).get('mysql_engine','').lower()=='innodb','MYSQL_INNODB_REQUIRED')
            require(i.get_pk_constraint(t.name)['constrained_columns']==[x.name for x in t.primary_key],'MYSQL_PRIMARY_KEY_MISMATCH')
            checks={x['name']:normalized_expression(x['sqltext']) for x in i.get_check_constraints(t.name)}
            uniques={tuple(x['column_names']) for x in i.get_indexes(t.name) if x.get('unique')}
            fks={(tuple(f['constrained_columns']),f['referred_table'],tuple(f['referred_columns'])) for f in i.get_foreign_keys(t.name)}
            for col in t.c:
                require(cols[col.name]['nullable']==col.nullable,'MYSQL_NULLABILITY_MISMATCH')
                if col.computed:
                    found=cols[col.name].get('computed',{});counts['computed_columns']+=1
                    require(found.get('persisted') and normalized_expression(found['sqltext'])==normalized_expression(col.computed.sqltext),'MYSQL_GENERATED_COLUMN_MISMATCH')
            for k in t.constraints:
                if k.__class__.__name__=='CheckConstraint':
                    counts['checks']+=1;require(checks.get(k.name)==normalized_expression(k.sqltext),'MYSQL_CHECK_DEFINITION_MISMATCH:'+str(k.name))
                if k.__class__.__name__=='UniqueConstraint':
                    counts['unique_guards']+=1;require(tuple(x.name for x in k.columns) in uniques,'MYSQL_UNIQUE_GUARD_MISMATCH')
            for f in t.foreign_keys:
                counts['foreign_keys']+=1;require(((f.parent.name,),f.column.table.name,(f.column.name,)) in fks,'MYSQL_FOREIGN_KEY_MISMATCH')
            counts['tables']+=1
    return counts


def grants(c, schema):
    """Separate runtime and panel actors; neither receives DDL, DELETE or admin rights."""
    from production_guard import required_grants
    runtime=required_grants()
    runtime['device_enrollment_revisions'].add(('INSERT',None))
    for t in ('classroom_wifi_policies','wifi_classrooms','session_classroom_requirements'):runtime.setdefault(t,set()).add(('SELECT',None))
    for t in ('classroom_wifi_challenges','attempt_classroom_requirements','attendance_wifi_bindings','classroom_ble_challenges'):
        runtime[t]={('SELECT',None),('INSERT',None),('UPDATE',None)}
    runtime['classroom_ble_policies']={('SELECT',None)}
    for t in ('classroom_wifi_events','classroom_ble_events'):runtime[t]={('INSERT',None)}
    for table, permissions in runtime.items():
        for verb,col in permissions:
            c.exec_driver_sql(f'GRANT {verb}'+(f' (`{col}`)' if col else '')+f' ON `{schema}`.`{table}` TO \'{ACTORS["runtime"]}\'@\'127.0.0.1\'')
    for t in ('courses','class_schedules','class_sessions','student_groups','attendance','wifi_classrooms',
              'network_policies','network_policy_events','classroom_wifi_policies','classroom_wifi_policy_events',
              'classroom_ble_policies','classroom_ble_policy_events','session_classroom_requirements','verification_challenges'):
        c.exec_driver_sql(f"GRANT SELECT ON `{schema}`.`{t}` TO '{ACTORS['operator']}'@'127.0.0.1'")
    for t in ('class_schedules','class_sessions','network_policies','classroom_wifi_policies','classroom_ble_policies','wifi_classrooms','session_classroom_requirements'):
        c.exec_driver_sql(f"GRANT INSERT,UPDATE ON `{schema}`.`{t}` TO '{ACTORS['operator']}'@'127.0.0.1'")
    for t in ('network_policy_events','classroom_wifi_policy_events','classroom_ble_policy_events'):
        c.exec_driver_sql(f"GRANT INSERT ON `{schema}`.`{t}` TO '{ACTORS['operator']}'@'127.0.0.1'")
    # Existing session creation serializes on its group via FOR UPDATE. Permit
    # that lock without granting permission to edit school groups or students.
    c.exec_driver_sql(f"GRANT LOCK TABLES ON `{schema}`.* TO '{ACTORS['operator']}'@'127.0.0.1'")
    # Schema visibility for the panel's prerequisite check, without reading
    # signed observation data or granting DDL to the operator.
    for t in ('attempt_classroom_requirements','attendance_wifi_bindings'):
        c.exec_driver_sql(f"GRANT REFERENCES ON `{schema}`.`{t}` TO '{ACTORS['operator']}'@'127.0.0.1'")


def schema_setup(e):
    # Explicit offline operator step, never called by app or panel startup.
    tables=all_tables()
    for t in tables:t.create(e,checkfirst=True)
    from modules.devices.two_device_migration import upgrade_two_device_schema
    from modules.devices.pending_migration import upgrade_pending_schema
    from modules.devices.biometric_migration import upgrade_biometric_schema
    from modules.devices.activation_migration import upgrade_activation_schema
    from modules.devices.replacement_migration import upgrade_replacement_schema
    from modules.devices.management_migration import upgrade_management_schema
    from modules.networks.migration import upgrade_network_schema
    from modules.authorization.migration import upgrade_attendance_authorization_schema
    operations=[upgrade_two_device_schema,upgrade_pending_schema,upgrade_biometric_schema,upgrade_activation_schema,
        upgrade_replacement_schema,upgrade_management_schema,upgrade_network_schema,upgrade_attendance_authorization_schema]
    for operation in operations:operation(e)
    return verify_schema(e)


def clean_case(control,name):
    """Acceptance-only cleanup: remove test grants as well as test tables."""
    from sqlalchemy import text
    require(re.fullmatch(r'fypmysqlcase_[0-9a-f]{12}',name),'MYSQL_UNSAFE_TEST_CLEANUP')
    allowed={"'"+ACTORS[r]+"'@'127.0.0.1'" for r in ('runtime','operator')}
    with control.begin() as c:
        targets=c.execute(text('SELECT TABLE_NAME,GRANTEE FROM information_schema.TABLE_PRIVILEGES WHERE TABLE_SCHEMA=:s UNION SELECT TABLE_NAME,GRANTEE FROM information_schema.COLUMN_PRIVILEGES WHERE TABLE_SCHEMA=:s'),dict(s=name)).all()
        for table,actor in targets:
            require(re.fullmatch(r'[a-zA-Z0-9_]+',table) and actor in allowed,'MYSQL_TEST_GRANT_TARGET_REJECTED')
            c.exec_driver_sql('REVOKE ALL PRIVILEGES ON `'+name+'`.`'+table+'` FROM '+actor)
        actors=c.execute(text('SELECT DISTINCT GRANTEE FROM information_schema.SCHEMA_PRIVILEGES WHERE TABLE_SCHEMA=:s'),dict(s=name)).scalars().all()
        for actor in actors:
            require(actor in allowed,'MYSQL_TEST_SCHEMA_GRANT_REJECTED')
            c.exec_driver_sql('REVOKE ALL PRIVILEGES ON `'+name+'`.* FROM '+actor)
        c.exec_driver_sql('DROP DATABASE IF EXISTS `'+name+'`')


def command(env,p,role):
    if role=='database':return [str(env/'runtime/bin/mysqld.exe'),'--defaults-file='+str(env/'server.ini'),'--console']
    return [sys.executable,'-B',str(Path(__file__).resolve()),'serve-'+role,'--environment',str(env)]


def owned(env,p,role):
    import disposable_processes as processes
    args=command(env,p,role)
    return processes.verified_pid(env,role,args,[args[0],sys._base_executable] if role!='database' else [args[0]],
        p[{'database':'db_port','backend':'backend_port','panel':'panel_port'}[role]])


def launch(env,p,role):
    import disposable_processes as processes
    require((env/'server.ini').read_text()==server_config(env,p),'MYSQL_NATIVE_CONFIG_CHANGED')
    pid=owned(env,p,role)
    if pid:return processes.ObservedProcess(pid)
    if role!='database':(env/(role+'.stop')).unlink(missing_ok=True)
    args=command(env,p,role)
    clean={k:v for k,v in os.environ.items() if not k.startswith(('DB_','MYSQL_','BIOMETRIC_','FYP_','ATTENDANCE_'))}
    with (env/(role+'.log')).open('ab') as log:
        proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=log,stderr=log,cwd=ROOT,creationflags=QUIET,env=clean)
    processes.register(env,role,proc.pid,args,[args[0],sys._base_executable] if role!='database' else [args[0]])
    return proc


def wait_db(env,p,proc,seconds=40):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        require(proc.poll() is None,'MYSQL_SERVER_EXITED: inspect private database.log')
        try:
            e=engine(env,p,'root');e.dispose();return
        except Exception:time.sleep(.25)
    raise RuntimeError('MYSQL_DATABASE_READINESS_TIMEOUT')


def backend_ready(env,p):
    import httpx
    require(owned(env,p,'backend') is not None,'MYSQL_BACKEND_PROCESS_MISMATCH')
    try:
        r=httpx.get(f'http://127.0.0.1:{p["backend_port"]}/manual-test/isolation',timeout=3,trust_env=False)
        r.raise_for_status();v=r.json()
        require(all(v.get(k)==value for k,value in {'disposable':True,'vendor':'mysql','db_port':p['db_port'],
            'database':p['db_name'],'server_uuid':p['server_uuid'],'account_bound_fyp':True,'production_port_blocked':True}.items()),'MYSQL_BACKEND_IDENTITY_MISMATCH')
        return {'classroom_wifi':True}
    except httpx.HTTPError:raise RuntimeError('MYSQL_BACKEND_NOT_READY') from None


def wait_http(env,p,proc,role):
    import httpx
    deadline=time.monotonic()+90
    port=p['backend_port'] if role=='backend' else p['panel_port']
    while time.monotonic()<deadline:
        require(proc.poll() is None,'MYSQL_'+role.upper()+'_EXITED: inspect private log')
        try:
            r=httpx.get(f'http://127.0.0.1:{port}/'+('manual-test/isolation' if role=='backend' else 'login'),timeout=2,trust_env=False)
            if r.status_code==200:
                if role=='backend':backend_ready(env,p)
                return
        except (httpx.HTTPError,RuntimeError):pass
        time.sleep(.25)
    raise RuntimeError('MYSQL_HTTP_READINESS_TIMEOUT')


def stop(env,p):
    import disposable_processes as processes
    # Validate every role before signalling any process.
    rows={role:owned(env,p,role) for role in ('panel','backend','database')}
    for role,pid in rows.items():
        if not pid:continue
        observed=processes.ObservedProcess(pid)
        if role=='database':
            e=engine(env,p,'root')
            try:
                raw=e.raw_connection()
                try:
                    raw.driver_connection.cmd_query('SHUTDOWN')
                finally:
                    raw.invalidate();raw.close()
            finally:e.dispose()
        else:(env/(role+'.stop')).touch()
        deadline=time.monotonic()+25
        while observed.poll() is None:
            require(time.monotonic()<deadline,'MYSQL_GRACEFUL_STOP_TIMEOUT');time.sleep(.25)
        processes.forget(env,role,pid)


def serve(env,p,role):
    import uvicorn
    checked=engine(env,p,'root')
    try:verify_schema(checked)
    finally:checked.dispose()
    if role=='backend':
        from application_factory import create_app
        settings=SimpleNamespace(**{k:p[k] for k in ('timezone','session_hours','challenge_seconds','face_threshold','demo_mode','fyp_account_bound_enrollment','biometric_key')})
        e=engine(env,p,'runtime');app=create_app(settings=settings,engine=e)
        from modules.classroom_wifi.router import router as wifi
        from modules.classroom_ble.router import router as ble
        from modules.classroom_wifi.attendance import AttendanceClassroomService
        app.include_router(wifi);app.include_router(ble)
        app.state.context.classroom_attendance=AttendanceClassroomService(app.state.context)
        @app.get('/manual-test/isolation',include_in_schema=False)
        def isolation():
            blocked=True
            for host in ('127.0.0.1','::1','localhost'):
                try:socket.create_connection((host,3306),timeout=.1);blocked=False
                except PermissionError:pass
                except OSError:blocked=False
            return dict(disposable=True,vendor='mysql',db_port=p['db_port'],database=p['db_name'],
                server_uuid=p['server_uuid'],account_bound_fyp=True,production_port_blocked=blocked)
        port=p['backend_port']
    else:
        from admin_testing import create_panel
        from admin_testing_launcher import credentials
        e=engine(env,p,'operator');app=create_panel(e,**credentials(env/'panel-admin.json'),
            ready=lambda:backend_ready(env,p),port=p['panel_port'],database_port=p['db_port'])
        port=p['panel_port']
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,proxy_headers=False,access_log=False,log_level='warning'))
    def watch():
        while not server.should_exit:
            if (env/(role+'.stop')).exists():server.should_exit=True;return
            time.sleep(.25)
    threading.Thread(target=watch,daemon=True).start()
    try:server.run()
    finally:e.dispose()


def setup(args):
    try:
        return _setup(args)
    except Exception:
        env=getattr(args,'created_environment',None)
        if env is not None:
            try:
                p=json.loads((env/'profile.json').read_text())
                if p['server_uuid']!='00000000-0000-0000-0000-000000000000':
                    stop(env,p)
                elif owned(env,p,'database'):
                    # Incomplete bootstrap: exact saved executable/command/port
                    # is verified before using only this new instance's secret.
                    import mysql.connector
                    values=json.loads((env/'secrets.json').read_text())
                    initialized=(env/'root-initialized').exists()
                    initial=re.search(rb'temporary password is generated for root@localhost: (\S+)',(env/'initializer-private.log').read_bytes())
                    password=values['root'] if initialized else initial[1].decode()
                    c=mysql.connector.connect(host='127.0.0.1',port=p['db_port'],user='root',password=password,
                        use_pure=True,client_flags=[mysql.connector.constants.ClientFlag.CAN_HANDLE_EXPIRED_PASSWORDS],connection_timeout=3)
                    try:
                        if not initialized:c.cmd_query("ALTER USER CURRENT_USER() IDENTIFIED BY '"+values['root']+"'")
                        c.cmd_query('SHUTDOWN')
                    finally:c.close()
            except Exception:
                print('MYSQL_INCOMPLETE_SETUP_CLEANUP_REQUIRED: failed private files retained; no foreign process was stopped.')
        raise


def _setup(args):
    # Existing pointer means resume/read existing configuration, never reseed.
    if (BASE/'current.json').exists() and not args.new_environment:
        env,p=load();print(json.dumps(dict(result='ALREADY_CONFIGURED',environment=str(env),next_action='Use status/start; no data changed')));return
    source=Path(args.mysql_home).resolve(strict=True)
    binary=source/'bin/mysqld.exe';require(binary.is_file(),'MYSQL_BINARY_NOT_FOUND')
    version=subprocess.run([str(binary),'--no-defaults','--version'],capture_output=True,text=True,timeout=10,creationflags=QUIET)
    match=re.search(r'\bVer (\d+\.\d+\.\d+)\b',version.stdout)
    require(version.returncode==0 and match and match[1] in SUPPORTED and 'MySQL Community Server' in version.stdout,'MYSQL_UNSUPPORTED_VERSION: tested release is 8.4.3 Community')
    ports=[args.db_port,args.backend_port,args.panel_port]
    require(len(set(ports))==3 and all(1024<=n<=65535 and n not in (3306,3322,8000,8002,8003) for n in ports),'MYSQL_PORTS_REJECTED')
    require(all(not 3306<=n<3400 for n in ports[1:]),'MYSQL_HTTP_PORT_IN_DATABASE_RANGE')
    for port in ports:
        with socket.socket() as s:
            s.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1);s.bind(('127.0.0.1',port))
    from prepare_manual_android_test import private_directory
    BASE.mkdir(parents=True,exist_ok=True)
    env=BASE/('env-'+secrets.token_hex(6));private_directory(env)
    args.created_environment=env
    secrets_map={role:secrets.token_urlsafe(40) for role in ACTORS}
    save(env/'secrets.json',secrets_map)
    from cryptography.fernet import Fernet
    p=dict(format=1,vendor='mysql',version=match[1],server_uuid='00000000-0000-0000-0000-000000000000',db_host='127.0.0.1',
        db_port=args.db_port,db_name='fypmysqltest_'+secrets.token_hex(6),backend_port=args.backend_port,panel_port=args.panel_port,
        expected_datadir=str(env/'data'),expected_basedir=str(env/'runtime'),biometric_key=Fernet.generate_key().decode(),
        timezone='Asia/Kuala_Lumpur',session_hours=8,challenge_seconds=90,face_threshold=.45,demo_mode=False,fyp_account_bound_enrollment=True)
    validate_profile(p,env);network_guard(p['db_port'])
    # Copy program resources only. A teammate's installation may contain a live
    # data/ folder or private my.ini; neither may enter the new environment.
    (env/'runtime').mkdir()
    for name in ('bin','lib','share'):
        folder=source/name
        if folder.is_dir():
            require(folder.resolve().is_relative_to(source),'MYSQL_RESOURCE_LINK_REJECTED')
            shutil.copytree(folder,env/'runtime'/name,ignore=shutil.ignore_patterns('*.ini','*.cnf','*.log','*.ibd','ibdata*','auto.cnf','*.pem','*.key'))
    (env/'tmp').mkdir();(env/'export').mkdir()
    initialized=subprocess.run([str(env/'runtime/bin/mysqld.exe'),'--no-defaults','--initialize','--basedir='+str(env/'runtime'),
        '--datadir='+str(env/'data'),'--console'],capture_output=True,timeout=120,creationflags=QUIET)
    (env/'initializer-private.log').write_bytes(initialized.stdout+initialized.stderr)
    require(initialized.returncode==0,'MYSQL_INITIALIZATION_FAILED: private initializer log retained')
    initial=re.search(rb'temporary password is generated for root@localhost: (\S+)',initialized.stderr)
    require(initial is not None,'MYSQL_INITIAL_PASSWORD_NOT_FOUND')
    config=server_config(env,p)
    (env/'server.ini').write_text(config);save(env/'profile.json',p)
    proc=launch(env,p,'database')
    import mysql.connector
    deadline=time.monotonic()+40;conn=None
    while time.monotonic()<deadline:
        require(proc.poll() is None,'MYSQL_BOOTSTRAP_SERVER_EXITED')
        try:
            conn=mysql.connector.connect(host='127.0.0.1',port=p['db_port'],user='root',password=initial[1].decode(),
                client_flags=[mysql.connector.constants.ClientFlag.CAN_HANDLE_EXPIRED_PASSWORDS],use_pure=True,connection_timeout=2,read_timeout=8,write_timeout=8);break
        except mysql.connector.Error:time.sleep(.25)
    require(conn is not None,'MYSQL_BOOTSTRAP_TIMEOUT')
    try:
        # Parameter conversion asks for @@sql_mode, which an expired-password
        # connection cannot read. This generated URL-safe secret needs no escaping.
        require(re.fullmatch(r'[A-Za-z0-9_-]{40,}', secrets_map['root']), 'MYSQL_BOOTSTRAP_SECRET_FORMAT')
        conn.cmd_query("ALTER USER CURRENT_USER() IDENTIFIED BY '"+secrets_map['root']+"'")
        (env/'root-initialized').touch()
        with conn.cursor() as c:
            c.execute('SELECT @@server_uuid');p['server_uuid']=c.fetchone()[0]
            c.execute('CREATE DATABASE `'+p['db_name']+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci')
            for role in ('runtime','operator'):
                c.execute("CREATE USER '"+ACTORS[role]+"'@'127.0.0.1' IDENTIFIED BY %s",(secrets_map[role],))
        conn.commit()
    finally:conn.close()
    save(env/'profile.json',p)
    e=engine(env,p,'root')
    try:
        report=schema_setup(e)
        from sqlalchemy.orm import Session
        from models import Programme,StudentGroup,Student,Course,ClassSchedule
        from modules.devices.management_models import SchoolProvisionedAccount
        from security import hash_password
        student_password=secrets.token_urlsafe(20)
        now=datetime.now().replace(microsecond=0)
        with Session(e) as db,db.begin():
            db.add(Programme(programme_code='MYSQLTEST',programme_name='Synthetic MySQL FYP'));db.flush()
            group=StudentGroup(programme_code='MYSQLTEST',group_name='MYSQL-A',year_of_study=3,semester=1,academic_year=now.year);db.add(group);db.flush()
            db.add(Student(student_id='MYSQLTEST01',group_id=group.group_id,name='Synthetic MySQL Student',email='mysqltest01@example.test',password_hash=hash_password(student_password),created_at=now))
            db.flush();db.add(SchoolProvisionedAccount(student_id='MYSQLTEST01',provisioning_reference='SYNTHETIC-MYSQL-SCHOOL-ROSTER',provisioned_at=now))
            db.add(Course(course_code='FYPATT01',course_name='Synthetic MySQL Class',credit_hour=3));db.flush()
            db.add(ClassSchedule(course_code='FYPATT01',group_id=group.group_id,day_of_week=now.strftime('%A'),class_type='Test',start_time=daytime(0),end_time=daytime(23,59),start_date=now.date(),end_date=now.date()+timedelta(days=365),lecturer='Synthetic operator'))
        with e.begin() as c:grants(c,p['db_name'])
        (env/'STUDENT_CREDENTIALS.txt').write_text('Synthetic student: MYSQLTEST01\nAssigned password: '+student_password+'\nFace enrollment not completed; no device registered. Keep private.\n')
        save(env/'SETUP_REPORT.json',dict(result='PASS',schema=report,original_database_accessed=False,records_copied=False))
        if not args.no_select:save(BASE/'current.json',dict(environment=str(env)))
    finally:
        e.dispose()
        stop(env,p)
    print(json.dumps(dict(result='SETUP_COMPLETE',environment=str(env),db_port=p['db_port'],backend_port=p['backend_port'],
        panel_port=p['panel_port'],student='MYSQLTEST01',private_student_credentials=str(env/'STUDENT_CREDENTIALS.txt'),
        next_action='admin-init then start; no existing database was changed')))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('setup','start','stop','status','admin-init','serve-backend','serve-panel'))
    parser.add_argument('--environment',type=Path);parser.add_argument('--mysql-home',type=Path)
    parser.add_argument('--new-environment',action='store_true',help='Explicitly create another disposable environment; never overwrite one')
    parser.add_argument('--no-select',action='store_true',help='Keep the current MySQL environment pointer unchanged')
    parser.add_argument('--db-port',type=int,default=3332);parser.add_argument('--backend-port',type=int,default=8012);parser.add_argument('--panel-port',type=int,default=8013)
    args=parser.parse_args(argv)
    try:
        if args.action=='setup':
            require(args.mysql_home is not None,'MYSQL_HOME_REQUIRED');setup(args);return 0
        env,p=load(args.environment);network_guard(p['db_port'])
        if args.action=='admin-init':
            from admin_testing_launcher import initialize_admin
            initialize_admin(env/'panel-admin.json');print('ADMIN_CREATED');return 0
        if args.action.startswith('serve-'):serve(env,p,args.action[6:]);return 0
        import disposable_processes as processes
        with processes.lifecycle_lock(env):
            if args.action=='stop':stop(env,p);print('MYSQL_TEST_SERVICES_STOPPED');return 0
            if args.action=='status':
                backend_ready(env,p);print(json.dumps(dict(result='READY',vendor='mysql',db_port=p['db_port'],database=p['db_name'],api_base_url=f'http://127.0.0.1:{p["backend_port"]}',panel_url=f'http://127.0.0.1:{p["panel_port"]}')));return 0
            try:
                proc=launch(env,p,'database');wait_db(env,p,proc)
                e=engine(env,p,'root')
                try:verify_schema(e)
                finally:e.dispose()
                proc=launch(env,p,'backend');wait_http(env,p,proc,'backend')
                if (env/'panel-admin.json').exists():
                    proc=launch(env,p,'panel');wait_http(env,p,proc,'panel')
                print(json.dumps(dict(result='READY',vendor='mysql',api_base_url=f'http://127.0.0.1:{p["backend_port"]}',
                    panel_url=f'http://127.0.0.1:{p["panel_port"]}',admin_setup_required=not (env/'panel-admin.json').exists())))
            except Exception:
                stop(env,p);raise
        return 0
    except KeyboardInterrupt:
        print('MYSQL_OPERATOR_CANCELLED');return 1
    except Exception as exc:
        if args.action=='admin-init':
            from admin_testing_launcher import failure
            failure('mysql_admin_initialization',exc);return 1
        # Only known constant guard codes/types, never connector messages or secrets.
        message=str(exc) if type(exc) is RuntimeError else type(exc).__name__
        print('MYSQL_TEST_REJECTED: '+message);return 1


if __name__=='__main__':raise SystemExit(main())
