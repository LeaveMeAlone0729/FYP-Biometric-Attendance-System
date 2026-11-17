"""Pinned partner-only LAN backend/panel. No original DB or Cloudflare fallback."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re

from cryptography.fernet import Fernet
from sqlalchemy import inspect, text

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
    value = json.loads(path.read_text(encoding='utf-8-sig'))
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
    require('mariadb' in row[0].lower(), 'LOCAL_XAMPP_MARIADB_REQUIRED')
    require((row[1],row[2]) == (value.db_port,value.db_name), 'LOCAL_DATABASE_IDENTITY_MISMATCH')
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
    p.add_argument('action',choices=('serve-backend','serve-panel','init-empty','init-admin'))
    p.add_argument('--lan',action='store_true')
    args=p.parse_args(argv)
    try:
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
        print('PARTNER_LOCAL_NOT_STARTED: '+(str(exc) if isinstance(exc,LocalError) else type(exc).__name__))
        return 1


if __name__=='__main__':
    raise SystemExit(main())
