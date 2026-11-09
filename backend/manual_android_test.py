"""Private, full-FYP Android test launcher. No production/default DB fallback."""
import argparse
import configparser
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sys
import subprocess
from types import SimpleNamespace

BASE = Path('C:/FYP/DB-DeviceManagement')
DB_PORT = 3322
HTTP_PORT = 8002
RUNTIME = 'fyp_manual_runtime'


class ManualTestGuardError(RuntimeError):
    pass


def require(condition, code):
    if not condition: raise ManualTestGuardError(code)


def validate_native_config(content,env):
    """Reject native-server options that could escape the disposable directory."""
    config=configparser.ConfigParser(interpolation=None,allow_no_value=True)
    config.read_string(content)
    require(config.sections()==['mysqld'] and not config.defaults(),'INVALID_DISPOSABLE_SERVER_CONFIG')
    section=config['mysqld']
    fixed={'port':'3322','bind-address':'127.0.0.1','skip-slave-start':None,
        'skip-log-bin':None,'event-scheduler':'OFF','aria-recover-options':'OFF',
        'myisam-recover-options':'OFF','local-infile':'0','innodb-buffer-pool-size':'64M',
        'default-storage-engine':'InnoDB','max-connections':'30','max-statement-time':'8',
        'character-set-server':'utf8mb4','collation-server':'utf8mb4_general_ci'}
    paths={'basedir':'runtime','datadir':'data','tmpdir':'tmp','pid-file':'server.pid','secure-file-priv':'export'}
    require(set(section)==set(fixed)|set(paths),'UNEXPECTED_NATIVE_SERVER_OPTION')
    require(all(section[k]==v for k,v in fixed.items()),'DISPOSABLE_SERVER_SECURITY_SETTING_CHANGED')
    require(all(Path(section[k]).resolve()==(env/name).resolve() for k,name in paths.items()),
        'DISPOSABLE_SERVER_PATH_CHANGED')
    return True


def validate_profile(p):
    expected={'db_host','db_port','db_name','db_user','db_password','expected_datadir',
        'biometric_key','timezone','session_hours','challenge_seconds','face_threshold',
        'demo_mode','fyp_account_bound_enrollment'}
    require(type(p) is dict and set(p)==expected,'EXPLICIT_PRIVATE_PROFILE_REQUIRED')
    require(p['db_host']=='127.0.0.1' and type(p['db_port']) is int and p['db_port']==DB_PORT,
        'DISPOSABLE_DATABASE_ENDPOINT_REQUIRED')
    require(p['db_user']==RUNTIME and re.fullmatch(r'fypdevicemgmt_restore_[0-9a-f]{12}',p['db_name'] or ''),
        'DISPOSABLE_ACCOUNT_SCHEMA_REQUIRED')
    require(isinstance(p['db_password'],str) and len(p['db_password'])>=32,'STRONG_PRIVATE_SECRET_REQUIRED')
    directory=Path(p['expected_datadir']).resolve()
    require(directory.is_relative_to(BASE.resolve()) and directory.name=='data'
        and directory.parent.name.startswith('manual-android-'),'DISPOSABLE_DIRECTORY_REQUIRED')
    require(p['demo_mode'] is False and p['fyp_account_bound_enrollment'] is True,'EXPLICIT_FYP_POLICY_REQUIRED')
    require(p['timezone']=='Asia/Kuala_Lumpur' and type(p['session_hours']) is int
        and 0<p['session_hours']<=8 and p['challenge_seconds']==90 and p['face_threshold']==0.45,
        'UNREVIEWED_BIOMETRIC_OR_SESSION_SETTINGS')
    from cryptography.fernet import Fernet
    try:Fernet(p['biometric_key'].encode('ascii'))
    except Exception:raise ManualTestGuardError('INVALID_DISPOSABLE_ENCRYPTION_KEY') from None
    return p


def load_profile(path):
    target=Path(path).resolve(strict=True)
    require(target.is_relative_to(BASE.resolve()) and target.name=='backend-profile.json',
        'PRIVATE_PROFILE_LOCATION_REQUIRED')
    def unique(pairs):
        result={}
        for k,v in pairs:
            require(k not in result,'DUPLICATE_PROFILE_FIELD');result[k]=v
        return result
    return validate_profile(json.loads(target.read_text(encoding='utf-8-sig'),object_pairs_hook=unique))


def install_network_guard():
    # use_pure=True below forces database sockets through this Python guard.
    def audit(event,args):
        if event=='socket.connect' and isinstance(args[1],tuple):
            host,port=args[1][:2]
            if port==3306:raise PermissionError('PRODUCTION_DATABASE_PORT_BLOCKED')
            if port in range(3307,3322) or (port in range(3323,3400)):
                raise PermissionError('OTHER_DATABASE_PORT_BLOCKED')
            if host not in ('127.0.0.1','::1','localhost'):
                raise PermissionError('NON_LOOPBACK_OUTBOUND_BLOCKED')
    sys.addaudithook(audit)


def guarded_engine(p):
    from sqlalchemy import create_engine,event,text
    from sqlalchemy.engine import URL
    url=URL.create('mysql+mysqlconnector',host=p['db_host'],port=p['db_port'],
        database=p['db_name'],username=p['db_user'],password=p['db_password'])
    engine=create_engine(url,hide_parameters=True,isolation_level='READ COMMITTED',pool_pre_ping=True,
        connect_args={'connection_timeout':3,'read_timeout':8,'write_timeout':8,'use_pure':True})
    @event.listens_for(engine,'do_connect')
    def endpoint(dialect,record,args,kwargs):
        require(kwargs.get('host')=='127.0.0.1' and kwargs.get('port')==DB_PORT
            and kwargs.get('database')==p['db_name'] and kwargs.get('user')==RUNTIME
            and kwargs.get('use_pure') is True,'DATABASE_CONNECTION_OVERRIDE_BLOCKED')
    with engine.connect() as c:
        port,schema,account,directory,version=c.execute(text('SELECT @@port,DATABASE(),CURRENT_USER(),@@datadir,@@version')).one()
        require((port,schema,account,version)==(DB_PORT,p['db_name'],RUNTIME+'@127.0.0.1','10.4.27-MariaDB')
            and Path(directory).resolve()==Path(p['expected_datadir']).resolve(), 'WRONG_DISPOSABLE_DATABASE')
    return engine


def create_manual_app(profile_path):
    p=load_profile(profile_path)
    install_network_guard()
    # Set every Settings input before importing existing config. Its setdefault
    # loader cannot adopt production DB credentials or encryption-key defaults.
    fields={'DB_HOST':'db_host','DB_PORT':'db_port','DB_NAME':'db_name','DB_USER':'db_user',
        'DB_PASSWORD':'db_password','BIOMETRIC_KEY':'biometric_key','APP_TIMEZONE':'timezone',
        'SESSION_HOURS':'session_hours','CHALLENGE_SECONDS':'challenge_seconds',
        'FACE_DISTANCE_THRESHOLD':'face_threshold','DEMO_MODE':'demo_mode',
        'FYP_ACCOUNT_BOUND_ENROLLMENT':'fyp_account_bound_enrollment'}
    for key,value in fields.items():os.environ[key]=str(p[value]).lower() if type(p[value]) is bool else str(p[value])
    from application_factory import create_app
    engine=guarded_engine(p)
    settings=SimpleNamespace(**{k:v for k,v in p.items() if k!='expected_datadir'})
    app=create_app(settings=settings,engine=engine)  # Real partner inference, never test doubles.
    from modules.classroom_wifi.router import router as classroom_wifi_router
    app.include_router(classroom_wifi_router)  # Optional Phase 2: disposable backend only.
    from modules.classroom_ble.router import router as classroom_ble_router
    app.include_router(classroom_ble_router)  # Standalone only; no attendance adapter.
    from modules.classroom_wifi.attendance import AttendanceClassroomService
    app.state.context.classroom_attendance=AttendanceClassroomService(app.state.context)
    app.state.manual_test_database=p['db_name']
    @app.get('/manual-test/isolation',include_in_schema=False)
    def isolation():
        # No secrets or configurable targets; the actual serving process proves
        # its audit guard rejects IPv4/IPv6/localhost before a SYN is sent.
        return {'disposable':True,'db_port':DB_PORT,'account_bound_fyp':True,
            'production_port_blocked':network_self_test()}
    return app


def network_self_test():
    outcomes=[]
    for family,host in ((socket.AF_INET,'127.0.0.1'),(socket.AF_INET6,'::1'),(socket.AF_INET,'localhost')):
        with socket.socket(family,socket.SOCK_STREAM) as s:
            s.settimeout(1)
            # Exercise the exact pre-connect audit event without ever allowing
            # an OS connection, even if the guard is broken/missing.
            try:sys.audit('socket.connect',s,(host,3306))
            except PermissionError as exc:
                require(str(exc)=='PRODUCTION_DATABASE_PORT_BLOCKED','UNEXPECTED_NETWORK_GUARD')
                outcomes.append(True)
            else:raise ManualTestGuardError('PRODUCTION_PORT_NOT_BLOCKED')
    return all(outcomes)


def validate_lan_config(config):
    require(type(config) is dict and set(config) in ({'address','subnet'},{'address','subnet','clients'}),'INVALID_LAN_CONFIG')
    require(not config.get('clients'),'LEGACY_DEVICE_IP_ALLOWLIST: restart with fyp-test.ps1 start --lan')
    address=ipaddress.IPv4Address(config['address'])
    subnet=ipaddress.IPv4Network(config['subnet'],strict=True)
    ranges=('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')
    require(any(subnet.subnet_of(ipaddress.IPv4Network(r)) for r in ranges)
        and address in subnet and address not in (subnet.network_address,subnet.broadcast_address),'PRIVATE_LAN_REQUIRED')
    return {'address':str(address),'subnet':str(subnet)}


def private_interfaces():
    # Fixed read-only command; no user input is interpolated into PowerShell.
    command="Get-NetIPAddress -AddressFamily IPv4 | ForEach-Object { $a=$_; $p=Get-NetConnectionProfile -InterfaceIndex $a.InterfaceIndex -ErrorAction SilentlyContinue; if ($p) { [PSCustomObject]@{address=$a.IPAddress;prefix=$a.PrefixLength;category=[string]$p.NetworkCategory;interface=$a.InterfaceAlias} } } | ConvertTo-Json -Compress"
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],
        capture_output=True,text=True,timeout=10,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    rows=json.loads(result.stdout or '[]')
    if isinstance(rows,dict):rows=[rows]
    return rows


def select_private_interface(interface=None):
    candidates=[]
    for row in private_interfaces():
        if row['category']!='Private' or (interface and row.get('interface')!=interface):continue
        try:
            candidates.append(validate_lan_config({'address':row['address'],
                'subnet':str(ipaddress.IPv4Network(f"{row['address']}/{row['prefix']}",strict=False))}))
        except (ValueError,ManualTestGuardError):continue
    require(len(candidates)==1,'SELECT_ONE_PRIVATE_INTERFACE_WITH_--interface')
    return candidates[0]


def require_private_interface(config):
    rows=private_interfaces()
    require(any(r['address']==config['address'] and r['category']=='Private'
        and ipaddress.IPv4Network(f"{r['address']}/{r['prefix']}",strict=False)==ipaddress.IPv4Network(config['subnet'])
        for r in rows),'APPROVED_PRIVATE_INTERFACE_REQUIRED')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile')
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    try:
        if args.self_test:
            install_network_guard();require(network_self_test(),'NETWORK_GUARD_FAILED')
            print('PASS: IPv4, IPv6 and localhost production-port attempts blocked before connection')
            return 0
        require(args.profile is not None,'EXPLICIT_PRIVATE_PROFILE_REQUIRED')
        profile_path=Path(args.profile).resolve()
        load_profile(profile_path)  # Validate location before looking for sibling configuration.
        lan_path=profile_path.parent/'lan-listener.json'
        lan=validate_lan_config(json.loads(lan_path.read_text())) if lan_path.exists() else None
        if lan:require_private_interface(lan)
        app=create_manual_app(args.profile)
        import uvicorn
        import threading,time
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=HTTP_PORT,
            proxy_headers=False,access_log=False,log_level='warning'))
        stop_file=Path(args.profile).resolve().parent/'backend.stop'
        def watch():
            while not server.should_exit:
                if stop_file.exists():server.should_exit=True;return
                time.sleep(.25)
        threading.Thread(target=watch,daemon=True).start()
        sockets=[]
        try:
            if lan:
                for host in ('127.0.0.1',lan['address']):
                    listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                    sockets.append(listener)
                    listener.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
                    listener.bind((host,HTTP_PORT))
                server.run(sockets=sockets)
            else:server.run()
        finally:
            for listener in sockets:listener.close()
        return 0
    except Exception as exc:
        code=str(exc) if isinstance(exc,ManualTestGuardError) else type(exc).__name__
        print('MANUAL_ANDROID_TEST_START_REJECTED: '+code,file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
