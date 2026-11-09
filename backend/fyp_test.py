"""One explicit disposable environment; no production Settings/default connection."""
import argparse
from datetime import datetime
import getpass
import json
import re
from pathlib import Path
import sys
import time
from manual_android_test import (BASE,DB_PORT,ManualTestGuardError,load_profile,
    install_network_guard,require,select_private_interface,validate_lan_config)

DEFAULT_ENV=BASE/'manual-android-20261106-033334-1f0285'
SIMULATION_ID='fyp-simulation'
SIMULATION_LABEL='SIMULATION ONLY - '


def policy_state(db,identifier=SIMULATION_ID):
    from modules.networks.models import NetworkPolicy
    row=db.get(NetworkPolicy,identifier)
    return None if row is None else dict(network_id=row.network_id,name=row.network_name,
        cidr=row.network_cidr,enabled=row.enabled)


def change_policy(db,command,*,cidr=None,snapshot=None,now=None,actor=None,identifier=SIMULATION_ID,name=None):
    """Reuse the existing audited policy store, never a transport allowlist."""
    from modules.networks.policies import put_policy
    from modules.networks.cidr import canonical_cidr
    require(isinstance(identifier,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',identifier),'INVALID_SIMULATION_POLICY_ID')
    current=policy_state(db,identifier)
    require(current is None or current['name'].startswith(SIMULATION_LABEL),'NON_SIMULATION_POLICY_NOT_MANAGED')
    if command in ('set','add'):
        if command=='add':require(current is None,'SIMULATION_POLICY_ALREADY_EXISTS')
        label=SIMULATION_LABEL+(name.strip() if name is not None else identifier)
        if current is not None and name is None:label=current['name']
        require(name is None or bool(name.strip()),'INVALID_SIMULATION_POLICY_NAME')
        target=dict(network_id=identifier,name=label,
            cidr=canonical_cidr(cidr),enabled=True)
    elif command in ('enable','disable','remove'):
        require(current is not None,'SIMULATION_POLICY_NOT_CONFIGURED')
        target={**current,'enabled':command=='enable'}
    elif command=='restore':
        require(type(snapshot) is dict and set(snapshot)=={'format','policy'}
            and snapshot['format']=='fyp-network-simulation-v1','INVALID_POLICY_SNAPSHOT')
        target=snapshot['policy']
        if target is None:
            if current is None:return None
            target={**current,'enabled':False}  # Retain referenced rows and audit history.
        require(type(target) is dict and set(target)=={'network_id','name','cidr','enabled'}
            and target['network_id']==identifier and isinstance(target['name'],str)
            and target['name'].startswith(SIMULATION_LABEL),'INVALID_SIMULATION_POLICY')
        canonical_cidr(target['cidr'])
    else:raise ValueError('Unsupported simulation policy command')
    put_policy(db,network_id=identifier,name=target['name'],cidr=target['cidr'],
        enabled=target['enabled'],actor=actor or getpass.getuser(),now=now or datetime.now(),
        audit_action='REMOVED' if command=='remove' else None)
    return policy_state(db,identifier)


def operator_engine(env,p):
    # Credentials are local/offline only. Never pass them through HTTP or argv.
    from sqlalchemy import create_engine,text,event
    from sqlalchemy.engine import URL
    a=json.loads((env/'operator.json').read_text())
    engine=create_engine(URL.create('mysql+mysqlconnector',host=p['db_host'],port=p['db_port'],
        username='fyp_manual_admin',password=a['admin_password'],database=p['db_name']),
        hide_parameters=True,pool_pre_ping=True,isolation_level='READ COMMITTED',
        connect_args={'use_pure':True,'connection_timeout':3,'read_timeout':8,'write_timeout':8})
    @event.listens_for(engine,'do_connect')
    def pin(dialect,record,args,kw):
        require(kw.get('host')=='127.0.0.1' and kw.get('port')==DB_PORT
            and kw.get('database')==p['db_name'] and kw.get('user')=='fyp_manual_admin'
            and kw.get('use_pure') is True,'OPERATOR_TARGET_CHANGED')
    try:
        with engine.connect() as c:
            port,schema,account,directory,version=c.execute(text('SELECT @@port,DATABASE(),CURRENT_USER(),@@datadir,@@version')).one()
            require(port==DB_PORT and schema==p['db_name'] and account=='fyp_manual_admin@127.0.0.1'
                and Path(directory).resolve()==Path(p['expected_datadir']).resolve()
                and version=='10.4.27-MariaDB','WRONG_DISPOSABLE_DATABASE')
    except Exception:
        engine.dispose();raise
    return engine


def stop_backend(env):
    from prepare_manual_android_test import verified_pid
    from disposable_processes import ObservedProcess,forget
    pid=verified_pid(env,'backend')
    if not pid:return
    observed=ObservedProcess(pid)
    (env/'backend.stop').touch()
    deadline=time.monotonic()+30
    while observed.poll() is None:
        require(time.monotonic()<deadline,'DISPOSABLE_BACKEND_STOP_TIMEOUT')
        time.sleep(.25)
    forget(env,'backend',pid)


def run_lifecycle(args,env,p):
    from prepare_manual_android_test import start as start_services,stop as stop_services
    if args.command=='stop':stop_services(env);print('DISPOSABLE_SERVICES_STOPPED');return 0
    path=env/'lan-listener.json'
    if args.lan or args.loopback:
        lan=select_private_interface(args.interface) if args.lan else None
        stop_backend(env)
        if path.exists():
            backup=env/('lan-listener.before-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.json')
            backup.write_bytes(path.read_bytes())
        if lan:path.write_text(json.dumps(lan,indent=2))
        elif path.exists():path.unlink()
    elif path.exists():validate_lan_config(json.loads(path.read_text()))
    try:start_services(env)
    except Exception:
        try:stop_services(env)
        except Exception:
            print('DISPOSABLE_CLEANUP_INCOMPLETE: inspect isolated state; no foreign process was authorized for termination.',file=sys.stderr)
        raise
    url='http://'+(json.loads(path.read_text())['address'] if path.exists() else '127.0.0.1')+':8002'
    print(json.dumps(dict(result='READY',api_base_url=url,db_port=DB_PORT,
        database=p['db_name'],attendance_network_authorized=False)))
    return 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment',type=Path,default=DEFAULT_ENV)
    commands=parser.add_subparsers(dest='command',required=True)
    start=commands.add_parser('start');mode=start.add_mutually_exclusive_group()
    mode.add_argument('--lan',action='store_true');mode.add_argument('--loopback',action='store_true')
    start.add_argument('--interface',help='Private adapter alias when more than one is available')
    commands.add_parser('stop');commands.add_parser('status')
    policy=commands.add_parser('policy');actions=policy.add_subparsers(dest='action',required=True)
    listing=actions.add_parser('list');listing.add_argument('--all',action='store_true',help='Include retired policies retained for audit history')
    for action in ('set','add'):
        put=actions.add_parser(action);put.add_argument('--id',required=action=='add',default=SIMULATION_ID)
        put.add_argument('--name');put.add_argument('--cidr',required=True)
        put.add_argument('--simulation',required=True,action='store_true')
    for action in ('enable','disable','remove'):
        sub=actions.add_parser(action);sub.add_argument('--id',required=action=='remove',default=SIMULATION_ID)
    export=actions.add_parser('export');export.add_argument('--output',required=True,type=Path);export.add_argument('--id',default=SIMULATION_ID)
    restore=actions.add_parser('restore');restore.add_argument('--input',required=True,type=Path);restore.add_argument('--id',default=SIMULATION_ID)
    sessions=commands.add_parser('session');session_actions=sessions.add_subparsers(dest='action',required=True)
    create=session_actions.add_parser('create');create.add_argument('--class',dest='course_code',required=True)
    create.add_argument('--group-id',type=int)
    create.add_argument('--classroom',help='Require this classroom Wi-Fi policy for the new test session')
    duration=create.add_mutually_exclusive_group()
    duration.add_argument('--minutes',type=int,help='Duration from now; default 30 minutes, same day only')
    duration.add_argument('--expires-at',help='ISO expiry time, e.g. 2026-11-06T18:00:00+08:00')
    listing=session_actions.add_parser('list');listing.add_argument('--class',dest='course_code')
    listing.add_argument('--all',action='store_true',help='Include expired and closed sessions; never show PINs or hashes')
    for action in ('close','expire'):
        control=session_actions.add_parser(action);control.add_argument('--id',type=int,required=True)
    requirement=session_actions.add_parser('classroom');requirement.add_argument('--id',type=int,required=True)
    requirement_mode=requirement.add_mutually_exclusive_group()
    requirement_mode.add_argument('--assign',metavar='CLASSROOM_ID');requirement_mode.add_argument('--remove',action='store_true')
    classroom=commands.add_parser('classroom',help='Disposable client-observed Wi-Fi simulation policies')
    wifi_actions=classroom.add_subparsers(dest='action',required=True)
    wifi_list=wifi_actions.add_parser('list');wifi_list.add_argument('--classroom');wifi_list.add_argument('--all',action='store_true')
    wifi_add=wifi_actions.add_parser('add');wifi_add.add_argument('--id',required=True)
    wifi_add.add_argument('--classroom',required=True);wifi_add.add_argument('--bssid',required=True)
    wifi_add.add_argument('--ssid');wifi_add.add_argument('--simulation',required=True,action='store_true')
    for action in ('enable','disable','retire'):
        wifi_control=wifi_actions.add_parser(action);wifi_control.add_argument('--id',required=True)
    ble=commands.add_parser('ble',help='Standalone experimental classroom BLE policies')
    ble_actions=ble.add_subparsers(dest='action',required=True)
    ble_list=ble_actions.add_parser('list');ble_list.add_argument('--classroom');ble_list.add_argument('--all',action='store_true')
    ble_add=ble_actions.add_parser('add');ble_add.add_argument('--id',required=True);ble_add.add_argument('--classroom',required=True)
    ble_add.add_argument('--uuid',required=True);ble_add.add_argument('--label');ble_add.add_argument('--minimum-samples',type=int,default=5)
    ble_add.add_argument('--threshold',type=int,default=-65);ble_add.add_argument('--max-age-seconds',type=int,default=15)
    ble_add.add_argument('--simulation',required=True,action='store_true')
    for action in ('enable','disable','remove'):
        ble_control=ble_actions.add_parser(action);ble_control.add_argument('--id',required=True)
    args=parser.parse_args(argv)
    try:
        env=args.environment.resolve(strict=True)
        p=load_profile(env/'backend-profile.json')
        require(env.name.startswith('manual-android-'),'PRIVATE_ENVIRONMENT_REQUIRED')
        install_network_guard()
        if args.command in ('start','stop'):
            from disposable_processes import lifecycle_lock
            with lifecycle_lock(env):return run_lifecycle(args,env,p)
        elif args.command=='status':
            import httpx
            from prepare_manual_android_test import verified_pid
            if not verified_pid(env,'backend'):
                print(json.dumps(dict(result='STOPPED',code='BACKEND_NOT_RUNNING',message='Run fyp-test.ps1 start --lan.')));return 1
            try:response=httpx.get('http://127.0.0.1:8002/manual-test/isolation',timeout=3,trust_env=False)
            except httpx.RequestError:
                print(json.dumps(dict(result='UNAVAILABLE',code='BACKEND_NOT_READY',message='Owned process exists but API is not ready.')));return 1
            response.raise_for_status();data=response.json()
            require(data.get('disposable') is True and data.get('db_port')==DB_PORT and data.get('production_port_blocked') is True,'STATUS_ISOLATION_CHECK_FAILED')
            print(json.dumps(dict(result='READY',**data)))
        elif args.command=='session':
            from manual_sessions import require_backend_ready,create_session,list_sessions,close_session
            from sqlalchemy.orm import Session
            from app_time import local_now
            from types import SimpleNamespace
            require_backend_ready(env)
            engine=operator_engine(env,p)
            try:
                now=local_now(SimpleNamespace(timezone=p['timezone']))
                with Session(engine) as db,db.begin():
                    if args.action=='create':
                        result=create_session(db,now=now,timezone=p['timezone'],course_code=args.course_code,
                            group_id=args.group_id,minutes=args.minutes,expires_at=args.expires_at,classroom_id=args.classroom)
                    elif args.action=='list':
                        result={'sessions':list_sessions(db,now=now,timezone=p['timezone'],
                            course_code=args.course_code,include_all=args.all)}
                    elif args.action=='classroom':
                        from modules.classroom_wifi.attendance import configure
                        from modules.classroom_wifi.models import SessionClassroom
                        if args.assign is not None or args.remove:
                            result=configure(db,session_id=args.id,classroom_id=args.assign,now=now)
                        else:
                            from models import ClassSession
                            require(db.get(ClassSession,args.id) is not None,'SESSION_NOT_FOUND')
                            row=db.get(SessionClassroom,args.id)
                            result={'session_id':args.id,'classroom_id':row.classroom_id if row else None,'revision':row.revision if row else 0}
                    else:
                        result=close_session(db,session_id=args.id,now=now,timezone=p['timezone'],expire=args.action=='expire')
                # Only after COMMIT. No plaintext PIN in DB, argv, logs or later listings.
                print(json.dumps(dict(result='OK',simulation_only=True,database=p['db_name'],**result),indent=2))
            finally:engine.dispose()
        elif args.command=='ble':
            from sqlalchemy.orm import Session
            from modules.classroom_ble.policies import listing,change
            from app_time import local_now
            from types import SimpleNamespace
            engine=operator_engine(env,p)
            try:
                with Session(engine) as db,db.begin():
                    if args.action=='list':result={'policies':listing(db,args.classroom,args.all)}
                    else:result={'policy':change(db,args.action,policy_id=args.id,now=local_now(SimpleNamespace(timezone=p['timezone'])),actor=getpass.getuser(),
                        classroom=getattr(args,'classroom',None),service_uuid=getattr(args,'uuid',None),label=getattr(args,'label',None),
                        minimum_samples=getattr(args,'minimum_samples',5),rssi_threshold=getattr(args,'threshold',-65),max_age_seconds=getattr(args,'max_age_seconds',15))}
                print(json.dumps(dict(result='OK',simulation_only=True,attendance_authorized=False,**result),indent=2))
            finally:engine.dispose()
        elif args.command=='classroom':
            from sqlalchemy.orm import Session
            from modules.classroom_wifi.policies import change,listing
            from app_time import local_now
            from types import SimpleNamespace
            engine=operator_engine(env,p)
            try:
                with Session(engine) as db,db.begin():
                    if args.action=='list':
                        result={'policies':listing(db,args.classroom,args.all)}
                    else:
                        result={'policy':change(db,args.action,policy_id=args.id,
                            classroom=getattr(args,'classroom',None),access_point=getattr(args,'bssid',None),
                            network_name=getattr(args,'ssid',None),actor=getpass.getuser(),
                            now=local_now(SimpleNamespace(timezone=p['timezone'])))}
                print(json.dumps(dict(result='OK',simulation_only=True,attendance_authorized=False,**result),indent=2))
            finally:engine.dispose()
        else:
            from sqlalchemy import select
            from sqlalchemy.orm import Session
            from modules.networks.models import NetworkPolicy,NetworkPolicyEvent
            engine=operator_engine(env,p)
            try:
                with Session(engine) as db,db.begin():
                    if args.action=='list':
                        rows=[]
                        for r in db.scalars(select(NetworkPolicy).order_by(NetworkPolicy.network_id)):
                            latest=db.scalar(select(NetworkPolicyEvent.action).where(NetworkPolicyEvent.network_id==r.network_id).order_by(NetworkPolicyEvent.event_id.desc()).limit(1))
                            removed=latest=='REMOVED' and not r.enabled
                            if removed and not args.all:continue
                            rows.append(dict(network_id=r.network_id,name=r.network_name,cidr=r.network_cidr,enabled=r.enabled,
                                simulation_only=r.network_name.startswith(SIMULATION_LABEL),removed=removed))
                        print(json.dumps(dict(simulation_only=True,database=p['db_name'],policies=rows),indent=2))
                    elif args.action=='export':
                        snapshot={'format':'fyp-network-simulation-v1','policy':policy_state(db,args.id)}
                        with args.output.open('x') as f:json.dump(snapshot,f,indent=2)
                        print('SIMULATION_POLICY_SNAPSHOT_SAVED')
                    else:
                        snapshot=json.loads(args.input.read_text()) if args.action=='restore' else None
                        result=change_policy(db,args.action,cidr=getattr(args,'cidr',None),snapshot=snapshot,
                            identifier=args.id,name=getattr(args,'name',None))
                        print(json.dumps(dict(simulation_only=True,policy=result,
                            retained_for_audit=args.action=='remove')))
            finally:engine.dispose()
        return 0
    except Exception as exc:
        code=str(exc) if isinstance(exc,(ManualTestGuardError,ValueError)) else type(exc).__name__
        print('FYP_TEST_FAILED: '+code+'; no production fallback',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
