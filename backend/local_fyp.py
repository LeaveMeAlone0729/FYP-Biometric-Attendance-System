"""Pinned partner-only LAN backend/panel. No original DB or Cloudflare fallback."""
import argparse
from dataclasses import replace
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import warnings

from cryptography.fernet import Fernet
from sqlalchemy import inspect, text
from database_compat import vendor

ROOT = Path(__file__).resolve().parent.parent


class LocalError(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise LocalError(code)


def private(root=ROOT):
    identifier = hashlib.sha256(str(root.resolve()).lower().encode()).hexdigest()[:12]
    return Path.home() / 'FYP-Partner-Local' / identifier


def load_profile(path=None):
    path = path or private() / 'settings.json'
    require(path.is_file(), 'LOCAL_PRIVATE_SETTINGS_MISSING_SEE_PARTNER_LOCAL_MODE_DOC')
    return validate_profile(json.loads(path.read_text(encoding='utf-8-sig')))


def validate_profile(value):
    fields = {'db_host','db_port','db_name','db_user','db_password','biometric_key',
              'fyp_account_bound_enrollment','ble_executable'}
    require(set(value) == fields, 'LOCAL_SETTINGS_FIELDS_INVALID')
    require(value['db_host'] == '127.0.0.1' and type(value['db_port']) is int
        and 1024 <= value['db_port'] <= 65535, 'LOCAL_LOOPBACK_DATABASE_REQUIRED')
    require(isinstance(value['db_name'], str) and re.fullmatch(r'[A-Za-z0-9_]{1,64}',value['db_name'])
        and value['db_name'].lower() not in {'attendance_proposal_xampp','mysql','sys','information_schema','performance_schema'},
        'LOCAL_OWN_DEVELOPMENT_SCHEMA_REQUIRED_ORIGINAL_FORBIDDEN')
    require(isinstance(value['db_user'],str) and value['db_user'] and value['db_user'].lower() != 'root'
        and isinstance(value['db_password'],str) and len(value['db_password']) >= 12, 'LOCAL_DEDICATED_DATABASE_CREDENTIALS_REQUIRED')
    require(type(value['fyp_account_bound_enrollment']) is bool and isinstance(value['ble_executable'],str),
            'LOCAL_POLICY_SETTINGS_INVALID')
    try:
        Fernet(value['biometric_key'].encode())
    except (ValueError, AttributeError):
        raise LocalError('LOCAL_OWN_BIOMETRIC_KEY_REQUIRED') from None
    return value


def configure():
    """Create only a private connection profile; never connect to or alter a DB."""
    folder = private()
    path = folder / 'settings.json'
    require(not path.exists() and not (folder / 'identity.json').exists(),
            'LOCAL_PROFILE_OR_IDENTITY_ALREADY_EXISTS_NO_OVERWRITE')
    require(sys.stdin.isatty(), 'LOCAL_INTERACTIVE_TERMINAL_REQUIRED')

    def secret(prompt):
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            try:
                return getpass.getpass(prompt)
            except getpass.GetPassWarning:
                raise LocalError('LOCAL_INTERACTIVE_SECRET_INPUT_REQUIRED') from None

    port = input('Laragon database port [3306]: ').strip() or '3306'
    require(port.isascii() and port.isdecimal(), 'LOCAL_DATABASE_PORT_INVALID')
    value = dict(db_host='127.0.0.1', db_port=int(port),
        db_name=input('Restored database name: ').strip(),
        db_user=input('Dedicated database username [fyp_local_app]: ').strip() or 'fyp_local_app',
        db_password=secret('Database password (at least 12 characters): '),
        biometric_key=secret('Existing database biometric key (Enter to reuse backend/.env): ').strip(),
        fyp_account_bound_enrollment=False, ble_executable='')
    if not value['biometric_key']:
        env = ROOT / 'backend/.env'
        require(env.is_file(), 'LOCAL_EXISTING_BIOMETRIC_KEY_NOT_FOUND')
        keys = [line.split('=', 1)[1].strip() for line in env.read_text(encoding='utf-8-sig').splitlines()
                if '=' in line and line.split('=', 1)[0].strip() == 'BIOMETRIC_KEY']
        require(len(keys) == 1 and bool(keys[0]), 'LOCAL_EXISTING_BIOMETRIC_KEY_NOT_FOUND')
        value['biometric_key'] = keys[0]
    validate_profile(value)
    folder.mkdir(parents=True, exist_ok=True)
    if os.name == 'nt':
        owner = os.environ['USERDOMAIN'] + '\\' + os.environ['USERNAME']
        result = subprocess.run(['icacls', str(folder), '/inheritance:r', '/grant:r',
            owner + ':(OI)(CI)F', 'SYSTEM:(OI)(CI)F'], capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW)
        require(result.returncode == 0, 'LOCAL_PRIVATE_PROFILE_PERMISSIONS_FAILED')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
    print('Local profile saved privately. No database was changed; no new biometric key was generated.')
    print('Profile: ' + str(path))


def settings(profile):
    from config import Settings
    # Every database/secret/assurance field is explicit; backend/.env cannot
    # redirect Local mode to the original database or turn on demo diagnostics.
    return replace(Settings(), db_host=profile['db_host'], db_port=profile['db_port'],
        db_name=profile['db_name'], db_user=profile['db_user'], db_password=profile['db_password'],
        biometric_key=profile['biometric_key'], demo_mode=False, network_ble_test_mode=False,
        fyp_account_bound_enrollment=profile['fyp_account_bound_enrollment'])


def engine(value):
    from original_fyp import bounded_engine
    return bounded_engine(value)  # Explicit supplied Settings; no original settings()/probe().


def database_identity(connection, value):
    row = connection.execute(text('SELECT VERSION(),@@port,DATABASE(),CURRENT_USER(),@@datadir,@@basedir')).one()
    try:
        kind = vendor(connection)
    except RuntimeError as exc:
        raise LocalError('LOCAL_UNSUPPORTED_DATABASE_VENDOR_OR_VERSION') from exc
    require(kind != 'mysql' or row[0].startswith('8.4.'), 'LOCAL_MYSQL_84_REQUIRED')
    require((row[1],row[2]) == (value.db_port,value.db_name), 'LOCAL_DATABASE_IDENTITY_MISMATCH')
    require(row[3].rsplit('@', 1)[0] == value.db_user, 'LOCAL_DATABASE_ACCOUNT_MISMATCH')
    return dict(version=row[0],port=row[1],schema=row[2],account=row[3],
        datadir=str(Path(row[4]).resolve()),basedir=str(Path(row[5]).resolve()),
        encryption_key_sha256=hashlib.sha256(value.biometric_key.encode()).hexdigest(),
        account_bound_fyp=value.fyp_account_bound_enrollment)


def public_identity(actual):
    return dict(environment='partner_local',db_port=actual['port'],database=actual['schema'],
        identity=hashlib.sha256(json.dumps(actual,sort_keys=True).encode()).hexdigest(),
        classroom_wifi=True,ble_experimental=True)


def probe(*, profile=None, folder=None, prompt=None, validate=True):
    profile = profile or load_profile()
    folder = folder or private()
    value = settings(profile)
    db = engine(value)
    try:
        with db.connect() as c:
            actual = database_identity(c,value)
            if validate:
                from original_fyp import validate_schema
                validate_schema(c)  # Existing read-only full application schema validator.
        path = folder/'identity.json'
        if path.exists():
            require(json.loads(path.read_text()) == actual, 'LOCAL_PINNED_DATABASE_OR_POLICY_CHANGED')
        else:
            require(prompt is not None, 'LOCAL_DATABASE_IDENTITY_NOT_PINNED')
            require(prompt(f'Confirm your OWN Local schema {value.db_name} on 127.0.0.1:{value.db_port}; type PIN: ') == 'PIN',
                    'LOCAL_DATABASE_PIN_NOT_CONFIRMED')
            folder.mkdir(parents=True,exist_ok=True)
            with path.open('x') as stream:
                json.dump(actual,stream,indent=2)
        return public_identity(actual)
    finally:
        db.dispose()


def initialize_empty(db):
    """Explicit offline EMPTY schema only; reuse existing table definitions.

    Never called by start/install. Never creates databases, seeds records,
    changes an existing table, or repairs an interrupted initialization.
    """
    from application_schema import application_tables
    with db.connect() as c:
        require(not inspect(c).get_table_names(), 'LOCAL_EMPTY_SCHEMA_REQUIRED_NO_EXISTING_TABLES_CHANGED')
        for table in application_tables():
            table.create(c,checkfirst=False)
            c.commit()


def backend_ready():
    import httpx
    expected = probe(validate=False)
    with httpx.Client(timeout=4,trust_env=False) as c:
        r=c.get('http://127.0.0.1:8000/local-fyp/identity')
        require(r.status_code==200 and r.json()==expected,'LOCAL_BACKEND_IDENTITY_MISMATCH')
    return {'classroom_wifi':True}


def create_backend():
    from application_factory import create_app
    from fastapi import Request, HTTPException
    profile=load_profile(); value=settings(profile); actual=probe(profile=profile)
    app=create_app(settings=value,engine=engine(value),classroom_features=True,
                   startup_validator=lambda *_:probe())
    app.state.lan_database_identity = actual['identity']
    @app.get('/local-fyp/identity',include_in_schema=False)
    def identity(request:Request):
        if request.client is None or request.client.host not in ('127.0.0.1','::1'):
            raise HTTPException(403,'Local operator only.')
        return actual
    return app


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('configure','check','serve-backend','serve-panel','init-empty','init-admin'))
    p.add_argument('--lan',action='store_true')
    args=p.parse_args(argv)
    try:
        if args.action=='configure':
            configure()
            return 0
        if args.action=='check':
            print(json.dumps(probe(prompt=input), indent=2))
            return 0
        profile=load_profile(); value=settings(profile)
        if args.action=='init-empty':
            require(input(f'Only initialize your EMPTY schema {value.db_name}; type EMPTY: ')=='EMPTY','LOCAL_EMPTY_INIT_NOT_CONFIRMED')
            db=engine(value)
            try:
                with db.connect() as c:
                    database_identity(c,value)
                initialize_empty(db)
            finally:db.dispose()
            print('LOCAL_EMPTY_SCHEMA_INITIALIZED_NO_ACCOUNTS_OR_BIOMETRICS_SEE_SETUP_DOC')
            return 0
        if args.action=='init-admin':
            from admin_testing_launcher import initialize_admin
            private().mkdir(parents=True,exist_ok=True)
            initialize_admin(private()/'panel-admin.json')
            print('LOCAL_ADMIN_CREATED')
            return 0
        import uvicorn
        if args.action=='serve-backend':
            app=create_backend();host='0.0.0.0' if args.lan else '127.0.0.1';port=8000
        else:
            from admin_testing import create_panel
            from admin_testing_launcher import credentials
            backend_ready()
            app=create_panel(engine(value),**credentials(private()/'panel-admin.json'),
                ready=backend_ready,timezone=value.timezone,database_port=value.db_port,simulation_only=True)
            host='127.0.0.1';port=8003
        if args.action=='serve-backend':
            from lan_discovery import run_backend
            run_backend(app,host=host,port=port,parent=private(),mode='Local',
                        database_identity=app.state.lan_database_identity)
        else:
            uvicorn.run(app,host=host,port=port,proxy_headers=False,access_log=False)
        return 0
    except Exception as exc:
        number = getattr(getattr(exc, 'orig', exc), 'errno', None)
        database_errors = {
            1045: 'LOCAL_DATABASE_ACCESS_DENIED_CHECK_DEDICATED_ACCOUNT',
            1049: 'LOCAL_DATABASE_SCHEMA_NOT_FOUND',
            1524: 'LOCAL_DATABASE_AUTH_PLUGIN_UNAVAILABLE_USE_MYSQL_CACHING_SHA2_ACCOUNT',
            2003: 'LOCAL_DATABASE_UNREACHABLE_CHECK_PORT_AND_START_LARAGON',
        }
        code = str(exc) if isinstance(exc,LocalError) else database_errors.get(number, type(exc).__name__)
        print('PARTNER_LOCAL_NOT_STARTED: '+code)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
