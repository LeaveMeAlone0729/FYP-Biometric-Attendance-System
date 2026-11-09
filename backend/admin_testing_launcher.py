"""Explicit localhost operator launcher. Never imports app/main or loads a default DB."""
import argparse
import getpass
import json
import os
import re
import tempfile
import warnings
from pathlib import Path


def credentials(path):
    from manual_android_test import require
    p = json.loads(path.read_text(encoding='utf-8-sig'))
    require(set(p) == {'username', 'password_hash'} and
        re.fullmatch(r'[A-Za-z0-9_.-]{3,40}', p['username']) is not None and
        re.fullmatch(r'pbkdf2_sha256\$600000\$[A-Za-z0-9+/=]+\$[A-Za-z0-9+/=]+', p['password_hash']) is not None,
        'INVALID_PRIVATE_ADMIN_CREDENTIALS')
    return p


def initialize_admin(path):
    """Validate interactively before touching the credential file; never overwrite."""
    from manual_android_test import require, ManualTestGuardError
    from security import hash_password
    require(not path.exists(), 'ADMIN_ALREADY_EXISTS')
    username = input('New local testing admin username (3-40 letters/digits/._-): ').strip()
    require(re.fullmatch(r'[A-Za-z0-9_.-]{3,40}', username) is not None, 'INVALID_ADMIN_USERNAME')
    password = None
    def secret_input(prompt):
        # Do not let getpass fall back to echoed password input in a redirected shell.
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            try:
                return getpass.getpass(prompt)
            except getpass.GetPassWarning:
                raise ManualTestGuardError('INTERACTIVE_SECRET_INPUT_REQUIRED') from None
    for _ in range(3):
        candidate = secret_input('New password (12-128 characters): ')
        if not 12 <= len(candidate) <= 128:
            print('PASSWORD_LENGTH_REQUIRED: use 12-128 characters. Try again; no credential file was created.')
            continue
        confirmation = secret_input('Confirm password: ')
        if candidate != confirmation:
            print('PASSWORD_CONFIRMATION_MISMATCH: passwords did not match. Try again; no credential file was created.')
            continue
        password = candidate
        break
    if password is None:
        raise ManualTestGuardError('PASSWORD_SETUP_ATTEMPTS_EXHAUSTED')
    # Hash/serialize BEFORE creating a file. Publish atomically without replacing
    # a racing initializer's file; the temporary file inherits the private ACL.
    value = json.dumps({'username': username, 'password_hash': hash_password(password)})
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                prefix='.panel-admin-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # Atomic create; FileExistsError instead of overwriting.
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def failure(stage, exc):
    """Safe stage/code only. Never echo a connector message, password or hash."""
    from manual_android_test import ManualTestGuardError
    if isinstance(exc, ManualTestGuardError):
        candidate = str(exc).split(':', 1)[0]
        code = candidate if re.fullmatch(r'[A-Z][A-Z0-9_]+', candidate) else 'GUARD_REJECTED'
    elif isinstance(exc, EOFError):
        code = 'INTERACTIVE_INPUT_REQUIRED'
    elif isinstance(exc, PermissionError):
        code = 'PRIVATE_FILE_ACCESS_DENIED'
    elif isinstance(exc, FileExistsError):
        code = 'ADMIN_ALREADY_EXISTS'
    elif isinstance(exc, FileNotFoundError):
        code = 'ADMIN_CREDENTIALS_MISSING' if stage == 'credentials' else 'REQUIRED_PRIVATE_FILE_MISSING'
    elif isinstance(exc, (json.JSONDecodeError, UnicodeError)):
        code = 'INVALID_PRIVATE_FILE_ENCODING_OR_JSON'
    elif isinstance(exc, KeyboardInterrupt):
        code = 'OPERATOR_CANCELLED'
    else:
        code = 'STARTUP_STEP_FAILED'
    hints = {
        'ADMIN_CREDENTIALS_MISSING': 'Run start-admin-testing.ps1 -InitAdmin once in an interactive PowerShell terminal.',
        'INTERACTIVE_INPUT_REQUIRED': 'Run -InitAdmin directly in an interactive terminal, without piping input.',
        'INTERACTIVE_SECRET_INPUT_REQUIRED': 'Use an interactive PowerShell terminal supporting hidden password input; do not pipe passwords.',
        'ADMIN_ALREADY_EXISTS': 'Existing credentials were preserved. Start without -InitAdmin.',
        'PRIVATE_FILE_ACCESS_DENIED': 'Check access to the existing private environment; do not run as administrator or change production permissions.',
        'PASSWORD_SETUP_ATTEMPTS_EXHAUSTED': 'Retry -InitAdmin with a matching password of 12-128 characters.',
        'INVALID_ADMIN_USERNAME': 'Use a username of 3-40 letters/digits/._-.',
    }
    print(f'ADMIN_PANEL_NOT_STARTED: stage={stage}; code={code}; error_type={type(exc).__name__}. '
          + hints.get(code, 'Check the named startup step; no fallback was used.'))


def backend_probe(port, environment=None):
    """Ordinary main:app does not provide this isolation contract: fail closed."""
    import httpx
    from manual_android_test import require, ManualTestGuardError
    require(port in (8000, 8002), 'EXPECTED_LOCAL_BACKEND_PORT')
    if environment is not None:
        from prepare_manual_android_test import verified_pid
        require(verified_pid(environment, 'backend') is not None, 'BACKEND_PROCESS_PROFILE_MISMATCH')
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=3, trust_env=False,
                          follow_redirects=False) as client:
            result = client.get('/manual-test/isolation')
            result.raise_for_status()
            value = result.json()
            require(value.get('disposable') is True and value.get('db_port') == 3322
                    and value.get('account_bound_fyp') is True and value.get('production_port_blocked') is True,
                    'BACKEND_ISOLATION_MISMATCH')
            schema = client.get('/openapi.json')
            schema.raise_for_status()
            return {'classroom_wifi': '/api/v1/classroom-wifi/attendance-challenges' in schema.json().get('paths', {})}
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        raise ManualTestGuardError('BACKEND_NOT_READY_OR_NOT_ISOLATED: use the validated disposable backend, never a production fallback.') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', type=Path, help='Existing private manual-android environment directory')
    parser.add_argument('--init-admin', action='store_true', help='Prompt once; write only a password hash outside Git')
    parser.add_argument('--check-only', action='store_true', help='Read-only DB/schema and backend checks; no server')
    parser.add_argument('--backend-port', type=int, choices=(8000, 8002), default=8002)
    args = parser.parse_args(argv)
    engine = None
    stage = 'imports'
    try:
        from fyp_test import DEFAULT_ENV, operator_engine
        from manual_android_test import load_profile, install_network_guard, require
        stage = 'environment'
        env = (args.environment or DEFAULT_ENV).resolve(strict=True)
        stage = 'profile'
        profile = load_profile(env / 'backend-profile.json')
        path = env / 'panel-admin.json'
        if args.init_admin:
            require(not args.check_only, 'CHOOSE_ONE_OPERATION')
            stage = 'admin_initialization'
            initialize_admin(path)
            print('ADMIN_CREATED: password hash stored only in the existing private environment directory.')
            return 0
        # A readiness check must be useful before credentials are initialized.
        # Normal server startup still requires credentials before any DB access.
        auth = None
        if not args.check_only or path.exists():
            stage = 'credentials'
            auth = credentials(path)
        stage = 'network_guard'
        install_network_guard()
        stage = 'backend_identity_and_readiness'
        capabilities = backend_probe(args.backend_port, environment=env)
        stage = 'database_identity'
        engine = operator_engine(env, profile)  # Validates real port/schema/account/datadir/version.
        if args.check_only:
            stage = 'schema_inventory'
            from sqlalchemy import inspect
            tables = set(inspect(engine).get_table_names())
            print(json.dumps(dict(result='PASS' if auth else 'SETUP_REQUIRED', db_port=3322, backend_port=args.backend_port,
                classroom_wifi=capabilities['classroom_wifi'], ble_schema='classroom_ble_policies' in tables,
                backend_and_database='PASS', admin_credentials='PRESENT' if auth else 'MISSING',
                next_action='Start panel' if auth else 'Run start-admin-testing.ps1 -InitAdmin',
                panel_url='http://127.0.0.1:8003', production_fallback=False)))
            return 0 if auth else 1
        stage = 'panel_composition'
        from admin_testing import create_panel
        import uvicorn
        app = create_panel(engine, **auth, ready=lambda: backend_probe(args.backend_port, environment=env), timezone=profile['timezone'])
        print('LOCAL ADMIN PANEL: http://127.0.0.1:8003/login (Ctrl+C to stop)')
        stage = 'listener'
        uvicorn.run(app, host='127.0.0.1', port=8003, proxy_headers=False, access_log=False, reload=False)
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        # Never print connection exceptions, form values, tokens or credentials.
        failure(stage, exc)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
