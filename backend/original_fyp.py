"""One original FYP environment. No database creation, reseeding or fallback targets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from manual_android_test import ManualTestGuardError, require

ROOT = Path(__file__).resolve().parent
PRIVATE = Path.home() / 'FYP-Original-Local'
TARGET = ('127.0.0.1', 3306, 'attendance_proposal_xampp')


def settings():
    from config import Settings
    value = Settings()
    require((value.db_host, value.db_port, value.db_name) == TARGET,
            'ORIGINAL_CONFIGURATION_MISMATCH')
    require(bool(value.biometric_key), 'ORIGINAL_ENCRYPTION_KEY_MISSING')
    return value


def private_directory():
    PRIVATE.mkdir(exist_ok=True)
    if os.name == 'nt':
        owner = os.environ['USERDOMAIN'] + '\\' + os.environ['USERNAME']
        subprocess.run(['icacls', str(PRIVATE), '/inheritance:r', '/grant:r',
                        owner + ':(OI)(CI)F', 'SYSTEM:(OI)(CI)F'],
                       capture_output=True, check=True, timeout=10,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    return PRIVATE


def bounded_engine(value):
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    url = URL.create('mysql+mysqlconnector', username=value.db_user,
                     password=value.db_password, host=value.db_host,
                     port=value.db_port, database=value.db_name)
    return create_engine(url, pool_pre_ping=True, isolation_level='READ COMMITTED',
        connect_args=dict(use_pure=True, connection_timeout=3, read_timeout=5, write_timeout=5),
        hide_parameters=True)


def identity(connection, value):
    from sqlalchemy import text
    row = connection.execute(text('SELECT VERSION(),@@port,DATABASE(),CURRENT_USER(),@@datadir,@@basedir')).one()
    require((row[1], row[2]) == TARGET[1:], 'ORIGINAL_DATABASE_IDENTITY_MISMATCH')
    return dict(version=row[0], port=row[1], schema=row[2], account=row[3],
                datadir=str(Path(row[4]).resolve()), basedir=str(Path(row[5]).resolve()),
                encryption_key_sha256=hashlib.sha256(value.biometric_key.encode()).hexdigest())


def validate_schema(connection):
    from sqlalchemy import inspect
    from application_schema import application_tables
    from database_compat import verify_check_enforcement
    from modules.devices.pending_migration import verify_table
    inspector = inspect(connection)
    existing = set(inspector.get_table_names())
    expected = application_tables()
    missing = sorted(table.name for table in expected if table.name not in existing)
    require(not missing, 'ORIGINAL_SCHEMA_MISSING_TABLES:' + ','.join(missing))
    verify_check_enforcement(connection)
    for table in expected:
        actual = {column['name'] for column in inspector.get_columns(table.name)}
        require(set(table.columns.keys()) <= actual,
                'ORIGINAL_SCHEMA_MISSING_COLUMNS:' + table.name)
        # Reuse the existing read-only migration validator: types, nullability,
        # primary/foreign/unique keys, CHECKs and generated-column expressions.
        # This does not call any migration or temporary-table probe.
        verify_table(connection, table)


def probe(*, schema=True, pin=False):
    """Read actual application tables, not just SELECT 1 or process existence."""
    from sqlalchemy import text
    value = settings()
    engine = bounded_engine(value)
    try:
        with engine.connect() as connection:
            actual = identity(connection, value)
            # Empty tables are valid. Bounded connector reads also cover engine stalls.
            for name in ('students', 'attendance', 'registered_devices'):
                connection.execute(text('SELECT 1 FROM `' + name + '` LIMIT 1')).all()
            if schema:
                validate_schema(connection)
        path = PRIVATE / 'identity.json'
        if path.exists():
            require(json.loads(path.read_text()) == actual, 'ORIGINAL_PINNED_IDENTITY_CHANGED')
        elif pin:
            private_directory()
            with path.open('x') as stream:
                json.dump(actual, stream)
        return actual
    finally:
        engine.dispose()


def public_identity(actual):
    # No account, directory, key or private profile contents are served.
    digest = hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()
    return dict(environment='original', db_port=3306, database=TARGET[2],
                identity=digest, classroom_wifi=True, ble_experimental=True)


def create_backend(*, local_demo_slot2=False):
    from application_factory import create_app
    from fastapi import Request, HTTPException
    value = settings()
    actual = probe(pin=True)
    engine = bounded_engine(value)
    app = create_app(settings=value, engine=engine, classroom_features=True,
                     startup_validator=lambda *_: probe())

    if local_demo_slot2:
        from modules.devices.local_demo import CREDENTIAL
        key = (PRIVATE / 'local-demo-slot2.key').read_bytes()
        require(value.demo_mode and len(key) == 32, 'LOCAL_DEMO_SLOT2_CREDENTIAL_REQUIRED')
        app.state.sessions.configure(info={**app.state.sessions.kw['info'], CREDENTIAL: key})

        @app.get('/local-fyp/demo-slot2', include_in_schema=False)
        def local_demo_status(request: Request):
            if request.client is None or request.client.host not in ('127.0.0.1', '::1'):
                raise HTTPException(403, 'Local operator only.')
            return {'credential_sha256': hashlib.sha256(key).hexdigest()}

    @app.get('/local-fyp/identity', include_in_schema=False)
    def local_identity(request: Request):
        if request.client is None or request.client.host not in ('127.0.0.1', '::1'):
            raise HTTPException(403, 'Local operator only.')
        return public_identity(actual)
    return app


def backend_ready():
    import httpx
    # Full column inventory is verified at backend startup. Subsequent panel
    # checks still pin the actual server and read application tables, without
    # repeating 43-table metadata introspection on every form/page request.
    expected = public_identity(probe(schema=False))
    with httpx.Client(timeout=4, trust_env=False) as client:
        response = client.get('http://127.0.0.1:8000/local-fyp/identity')
        require(response.status_code == 200 and response.json() == expected,
                'ORIGINAL_BACKEND_IDENTITY_MISMATCH')
    return {'classroom_wifi': True}


def listening(port):
    with socket.socket() as sock:
        sock.settimeout(.3)
        return sock.connect_ex(('127.0.0.1', port)) == 0


def serve(role, *, lan=False, local_demo_slot2=False):
    import uvicorn
    if role == 'backend':
        app, port = create_backend(local_demo_slot2=local_demo_slot2), 8000
    else:
        from admin_testing import create_panel
        from admin_testing_launcher import credentials
        backend_ready()
        value = settings()
        app = create_panel(bounded_engine(value), **credentials(PRIVATE / 'panel-admin.json'),
            ready=backend_ready, timezone=value.timezone, database_port=3306, simulation_only=False)
        port = 8003
    host = '0.0.0.0' if role == 'backend' and lan else '127.0.0.1'
    uvicorn.run(app, host=host, port=port, proxy_headers=False, access_log=False)


def start():
    """Never adopt or terminate an unrelated service already occupying either port."""
    import httpx
    from disposable_processes import register
    probe(pin=True)  # No listeners start if actual tables or schema are unhealthy.
    require((PRIVATE / 'panel-admin.json').exists(), 'ORIGINAL_ADMIN_NOT_INITIALIZED')
    children = []
    images = [sys.executable, str(Path(sys.base_prefix) / 'python.exe')]
    try:
        for role, port in (('backend', 8000), ('panel', 8003)):
            if listening(port):
                if role == 'backend':
                    backend_ready()
                    continue
                # Matching process, creation time AND pinned backend are required.
                from disposable_processes import verified_pid
                args = [sys.executable, str(Path(__file__).resolve()), 'serve-panel']
                require(verified_pid(PRIVATE, role, args, images, port),
                        'ORIGINAL_PANEL_PORT_OCCUPIED')
                continue
            args = [sys.executable, str(Path(__file__).resolve()), 'serve-' + role]
            with (PRIVATE / (role + '.log')).open('ab') as log:
                child = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            children.append(child)
            register(PRIVATE, role, child.pid, args, images)
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                require(child.poll() is None, 'ORIGINAL_' + role.upper() + '_EXITED')
                try:
                    if role == 'backend':
                        backend_ready()
                    else:
                        with httpx.Client(timeout=2, trust_env=False) as client:
                            r = client.get('http://127.0.0.1:8003/login')
                            require(r.status_code == 200, 'ORIGINAL_PANEL_NOT_READY')
                    break
                except (httpx.HTTPError, ManualTestGuardError):
                    time.sleep(.5)
            else:
                raise ManualTestGuardError('ORIGINAL_STARTUP_TIMEOUT')
        return dict(result='READY', backend='http://127.0.0.1:8000',
                    panel='http://127.0.0.1:8003/login', database=TARGET[2], db_port=3306)
    except BaseException:
        # Only children created by THIS invocation, using live Popen handles.
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'start', 'admin-init', 'serve-backend', 'serve-panel'))
    parser.add_argument('--lan', action='store_true', help='Listen on LAN for serve-backend')
    parser.add_argument('--local-demo-slot2', action='store_true', help='Enable DEMO001 Slot 2 test evidence in the original demo server')
    args = parser.parse_args(argv)
    action = args.action
    if (args.lan or args.local_demo_slot2) and action != 'serve-backend':
        parser.error('LAN and local demo options require serve-backend')
    try:
        if action == 'admin-init':
            from admin_testing_launcher import initialize_admin
            initialize_admin(private_directory() / 'panel-admin.json')
            print('ADMIN_CREATED')
        elif action.startswith('serve-'):
            serve(action[6:], lan=args.lan, local_demo_slot2=args.local_demo_slot2)
        elif action == 'check':
            print(json.dumps(dict(result='READY', **public_identity(probe()))))
        else:
            private_directory()
            from disposable_processes import lifecycle_lock
            with lifecycle_lock(PRIVATE):
                print(json.dumps(start()))
        return 0
    except Exception as exc:
        # Driver exceptions can include credentials/SQL values. Never echo them.
        code = str(exc) if isinstance(exc, ManualTestGuardError) else 'DATABASE_OR_STARTUP_UNAVAILABLE'
        print(json.dumps(dict(result='BLOCKED', code=code, error_type=type(exc).__name__,
                              errno=getattr(getattr(exc, 'orig', exc), 'errno', None))))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
