"""Three-command original FYP workflow. No schema/data provisioning or fallback DB.

Windows effects are behind Host for isolated tests. Never import this module to
start services: all actions require explicit CLI invocation.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

import httpx

from disposable_processes import (canonical_path, lifecycle_lock, matches,
    query_process, record, split_command)

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_ROOT = Path(r'C:\FYP\FYP-Biometric-Attendance-System')
PUBLIC_HOST = 'api.bioattsys.xyz'
PUBLIC = 'https://' + PUBLIC_HOST
TUNNEL_NAME = 'fyp-attendance-gateway'
BEACON_UUID = 'b1ba7f4e-6931-49d5-99de-7e0caa159105'
QUIET = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
PORTS = {'backend': 8000, 'admin': 8003, 'gateway': 8004}


class Blocked(RuntimeError):
    pass


class BeaconExited(Blocked):
    pass


def require(condition, code):
    if not condition:
        raise Blocked(code)


def objects(value):
    return [] if value is None else value if isinstance(value, list) else [value]


def read_json(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def save_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def choose_device(devices, serial=None, prompt=input):
    rows = [line.split() for line in devices.splitlines()[1:] if line.strip()]
    ready = [row[0] for row in rows if len(row) >= 2 and row[1] == 'device']
    if serial:
        require(serial in ready, 'SELECTED_ANDROID_DISCONNECTED_OR_UNAUTHORIZED')
        return serial
    if len(ready) == 1 and ready[0] == '7732690b':
        return ready[0]
    require(bool(ready), 'NO_AUTHORIZED_ANDROID_DEVICE')
    choice = prompt('Type the exact target serial from the device list: ').strip()
    require(choice in ready, 'ANDROID_TARGET_SELECTION_REQUIRED')
    return choice


def ensure_identity(value, mode='Full'):
    if mode == 'Local':
        require(value.get('environment') == 'partner_local' and type(value.get('db_port')) is int
            and 1024 <= value['db_port'] <= 65535 and isinstance(value.get('database'),str)
            and value['database'].lower() != 'attendance_proposal_xampp'
            and isinstance(value.get('identity'),str) and len(value['identity']) == 64,
            'PARTNER_LOCAL_DATABASE_IDENTITY_MISMATCH')
        return
    require(value.get('environment') == 'original' and value.get('db_port') == 3306
            and value.get('database') == 'attendance_proposal_xampp'
            and isinstance(value.get('identity'), str) and len(value['identity']) == 64,
            'ORIGINAL_DATABASE_IDENTITY_MISMATCH')


def token_tunnel(arguments):
    """Return only the non-secret tunnel UUID. Never persist/print the token."""
    token = None
    if '--token' in arguments:
        token = arguments[arguments.index('--token') + 1]
    for argument in arguments:
        if argument.startswith('--token='):
            token = argument.split('=', 1)[1]
    if '--token-file' in arguments:
        # Service-owned files can be Administrator/SYSTEM-only. Do not read,
        # elevate, copy or change their ACLs just to identify the tunnel.
        return None
    if not token:
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(token + '=' * (-len(token) % 4)))
        value = data.get('t')
        require(isinstance(value, str) and re.fullmatch(r'[0-9a-fA-F-]{36}', value),
                'CLOUDFLARE_TUNNEL_ID_UNREADABLE')
        return value.lower()
    except (ValueError, KeyError, TypeError):
        raise Blocked('CLOUDFLARE_TUNNEL_ID_UNREADABLE') from None


class Host:
    def __init__(self, root=ROOT):
        self.root = root
        self.python = root / 'backend/venv/Scripts/python.exe'
        self.images = [str(self.python), str(Path(sys.base_prefix) / 'python.exe')]

    def command(self, args, *, timeout=15, capture=True, env=None):
        return subprocess.run([str(a) for a in args], cwd=self.root,
            capture_output=capture, text=True, timeout=timeout,
            creationflags=QUIET if capture else 0, env=env)

    def ps(self, command):
        result = self.command(['powershell.exe', '-NoProfile', '-NonInteractive',
                               '-Command', command])
        require(result.returncode == 0, 'WINDOWS_INSPECTION_FAILED')
        return json.loads(result.stdout) if result.stdout.strip() else None

    def guard(self):
        require(canonical_path(self.root.resolve()) == canonical_path(EXPECTED_ROOT), 'WRONG_REPOSITORY')
        require(self.python.is_file(), 'BACKEND_VENV_MISSING')
        branch = self.command(['git', 'branch', '--show-current'])
        require(branch.returncode == 0 and branch.stdout.strip() == 'SH', 'EXPECTED_BRANCH_SH')

    def lan(self):
        rows = objects(self.ps("Get-NetIPConfiguration | Where-Object { $_.NetAdapter.Status -eq 'Up' "
            "-and $_.NetAdapter.NdisPhysicalMedium -eq 9 -and $_.IPv4DefaultGateway } | "
            "ForEach-Object { $_.IPv4Address.IPAddress } | ConvertTo-Json -Compress"))
        import ipaddress
        valid = sorted(set(value for value in rows if isinstance(value, str)
            and isinstance(ipaddress.ip_address(value), ipaddress.IPv4Address)
            and not ipaddress.ip_address(value).is_loopback
            and not ipaddress.ip_address(value).is_link_local))
        require(len(valid) == 1, 'ONE_ACTIVE_WIFI_IPV4_REQUIRED')
        return valid[0]

    def listeners(self):
        return objects(self.ps("Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
            "Where-Object { $_.LocalPort -in 3306,8000,8003,8004,8005 } | "
            "Select-Object LocalAddress,LocalPort,OwningProcess | ConvertTo-Json -Compress"))

    def processes(self):
        # Never return cloudflared command lines to the caller/logs.
        return objects(self.ps("Get-CimInstance Win32_Process | Where-Object { "
            "$_.Name -in 'python.exe','BleProbe.exe' } | "
            "Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine,"
            "@{N='created_at';E={$_.CreationDate.ToUniversalTime().ToString('o')}} | ConvertTo-Json -Compress"))

    def process(self, pid):
        return query_process(pid)

    def database(self):
        import original_fyp
        # Existing bounded SELECT/schema validators; never pin/reseed/migrate here.
        require((original_fyp.PRIVATE / 'identity.json').is_file(), 'ORIGINAL_PINNED_IDENTITY_FILE_MISSING')
        return original_fyp.public_identity(original_fyp.probe())

    def db_start(self, logs, prompt):
        exe = Path(r'C:\xampp\mysql\bin\mysqld.exe')
        config = Path(r'C:\xampp\mysql\bin\my.ini')
        require(exe.is_file() and config.is_file(), 'APPROVED_XAMPP_INSTALLATION_MISSING')
        running = objects(self.ps("Get-CimInstance Win32_Process | Where-Object { $_.Name -in 'mysqld.exe','mariadbd.exe' } | "
            "Select-Object ExecutablePath | ConvertTo-Json -Compress"))
        require(not any(not p.get('ExecutablePath') or canonical_path(p['ExecutablePath']) == canonical_path(exe)
                        for p in running), 'XAMPP_MARIADB_PROCESS_ALREADY_EXISTS_NO_SECOND_START')
        require(prompt('MariaDB is stopped. Start existing C:\\xampp MariaDB with automatic Aria repair OFF? Type START: ') == 'START',
                'MARIADB_START_NOT_CONFIRMED')
        # Shared DB is intentionally NOT stored in owned-process shutdown state.
        with (logs / 'mariadb.log').open('ab') as log:
            subprocess.Popen([str(exe), '--defaults-file=' + str(config), '--standalone',
                '--console', '--aria-recover-options=OFF'], cwd=exe.parent,
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=QUIET)

    def http(self, path, *, public=False, gateway=False, lan=None):
        base = PUBLIC if public else ('http://' + lan + ':8000') if lan else (
            'http://127.0.0.1:8004' if gateway else 'http://127.0.0.1:8000')
        headers = {'Host': PUBLIC_HOST} if gateway else {}
        with httpx.Client(timeout=httpx.Timeout(8, connect=3), trust_env=False,
                          follow_redirects=False) as client:
            response = client.get(base + path, headers=headers)
            return response.status_code, response.json()

    def admin(self):
        with httpx.Client(timeout=3, trust_env=False, follow_redirects=False) as c:
            return c.get('http://127.0.0.1:8003/login').status_code == 200

    def cloudflare(self, runtime, prompt):
        # PathName may contain a tunnel secret. It stays in memory only.
        service = self.ps("Get-CimInstance Win32_Service -Filter \"Name='Cloudflared'\" | "
            "Select-Object State,ProcessId,PathName | ConvertTo-Json -Compress")
        require(service and service['State'] == 'Running', 'CLOUDFLARED_SERVICE_NOT_RUNNING_USE_EXISTING_SERVICE')
        args = split_command(service['PathName'])
        require(Path(args[0]).name.lower() == 'cloudflared.exe', 'UNEXPECTED_CLOUDFLARED_SERVICE_IMAGE')
        identifier = token_tunnel(args)
        if '--token-file' in args:
            token_path = Path(args[args.index('--token-file') + 1])
            try:
                metadata = token_path.stat()  # Attributes only, never token contents.
            except OSError:
                raise Blocked('CLOUDFLARE_TOKEN_FILE_METADATA_UNREADABLE_OPERATOR_SETUP_REQUIRED') from None
            binding = dict(name=TUNNEL_NAME,
                service_definition_sha256=hashlib.sha256(service['PathName'].encode()).hexdigest(),
                token_file_metadata_sha256=hashlib.sha256(json.dumps([
                    canonical_path(token_path), metadata.st_size, metadata.st_mtime_ns]).encode()).hexdigest())
            path = runtime / 'approved-tunnel.json'
            approved = read_json(path, {})
            if approved:
                require(all(approved.get(k) == v for k,v in binding.items())
                        and isinstance(approved.get('tunnel_id'), str), 'CLOUDFLARE_SERVICE_BINDING_CHANGED')
                return
            supplied = self.prompt_tunnel_id(prompt)
            require(prompt(f'Confirm in Cloudflare dashboard that {TUNNEL_NAME}, ID {supplied}, uses this laptop connector. Type CONFIRM: ') == 'CONFIRM',
                    'CLOUDFLARE_TUNNEL_MAPPING_NOT_CONFIRMED')
            save_json(path, dict(binding, tunnel_id=supplied, verification='operator-confirmed-protected-service'))
            return
        if not identifier:
            require('run' in args and args.index('run') + 1 < len(args)
                    and args[args.index('run') + 1] == TUNNEL_NAME,
                    'CLOUDFLARE_NAMED_TUNNEL_NOT_VERIFIABLE')
            return
        path = runtime / 'approved-tunnel.json'
        approved = read_json(path, {})
        expected = dict(name=TUNNEL_NAME, tunnel_id=identifier)
        if approved != expected:
            require(not approved, 'CLOUDFLARE_TUNNEL_ID_CHANGED')
            require(prompt(f'Confirm in Cloudflare dashboard that {TUNNEL_NAME} has ID {identifier}. Type CONFIRM: ') == 'CONFIRM',
                    'CLOUDFLARE_TUNNEL_MAPPING_NOT_CONFIRMED')
            save_json(path, expected)

    @staticmethod
    def prompt_tunnel_id(prompt):
        value = prompt('Cloudflare token file is private. Enter only the non-secret UUID of fyp-attendance-gateway from the dashboard: ').strip()
        try:
            return str(uuid.UUID(value))
        except (ValueError, AttributeError):
            raise Blocked('CLOUDFLARE_TUNNEL_UUID_REQUIRED_NO_TOKEN_INPUT') from None

    def source_beacon_path(self):
        home = Path(os.environ['TEMP']) / 'fyp-ble-probe-2e8a44c743da4761bec53f3ef493b974'
        return home / 'bin/Debug/net9.0-windows10.0.26100.0/BleProbe.exe'

    def beacon_path(self):
        return self.root / 'runtime/ble-beacon/BleProbe.exe'

    def beacon_locations(self):
        return [self.beacon_path(), self.source_beacon_path()]

    def assembly_identity(self, path):
        literal = str(path).replace("'", "''")
        return self.ps("$p='" + literal + "'; $a=[System.Reflection.AssemblyName]::GetAssemblyName($p); "
            "[pscustomobject]@{name=$a.Name;version=$a.Version.ToString();"
            "fileVersion=[System.Diagnostics.FileVersionInfo]::GetVersionInfo($p).FileVersion} | ConvertTo-Json -Compress")

    def beacon(self):
        exe = self.source_beacon_path()
        self.verify_beacon(exe)
        from ble_bundle import prepare, BundleError
        running = any(canonical_path(row.get('ExecutablePath') or '') == canonical_path(self.beacon_path())
                      for row in self.processes())
        try:
            return prepare(exe, self.beacon_path().parent, Path.home() / '.nuget/packages',
                           self.assembly_identity, running=running)
        except BundleError as exc:
            raise Blocked(str(exc)) from None

    def verify_beacon(self, exe):
        dll = exe.with_suffix('.dll')
        require(exe.is_file() and dll.is_file(), 'BLE_KNOWN_EXECUTABLE_MISSING')
        data = dll.read_bytes()
        require(BEACON_UUID.encode('utf-16-le') in data and b'GattServiceProvider' in data
                and '--continuous'.encode('utf-16-le') in data, 'BLE_IMPLEMENTATION_NOT_VERIFIED')

    def launch(self, args, role, logs):
        env = os.environ.copy()
        env['NETWORK_BLE_TEST_MODE'] = 'false'
        if getattr(self,'mode','Full')=='Full':
            env['FYP_PUBLIC_HOST'] = PUBLIC_HOST
        else:
            env.pop('FYP_PUBLIC_HOST',None)
        with (logs / (role + '.out.log')).open('ab') as out, (logs / (role + '.err.log')).open('ab') as err:
            child = subprocess.Popen(args, cwd=Path(args[0]).parent if role == 'beacon' else self.root,
                env=env, stdin=subprocess.DEVNULL,
                stdout=out, stderr=err, creationflags=QUIET)
        row = self.process(child.pid)
        if row is None:
            code = child.poll()
            raise Blocked(f'{role.upper()}_LAUNCH_EXITED exit_code={code}; log: {logs / (role + ".err.log")}')
        return child, row

    def stop(self, stored, args, images):
        row = self.process(stored['pid'])
        if row is None:
            return 'already exited'
        require(matches(row, args, images) and record(row) == stored, 'OWNED_PROCESS_IDENTITY_CHANGED_NO_STOP')
        # Open the exact process object and verify FILETIME, closing the PID-reuse race.
        import ctypes
        from ctypes import wintypes
        from datetime import datetime, timezone
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x101001, False, stored['pid'])
        require(bool(handle), 'OWNED_PROCESS_HANDLE_UNAVAILABLE')
        try:
            created, exited, cpu, user = (wintypes.FILETIME() for _ in range(4))
            require(kernel.GetProcessTimes(handle, *[ctypes.byref(x) for x in (created, exited, cpu, user)]),
                    'OWNED_PROCESS_TIME_UNREADABLE')
            delta = datetime.fromisoformat(stored['created_at']) - datetime(1601, 1, 1, tzinfo=timezone.utc)
            expected = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
            require(((created.dwHighDateTime << 32) | created.dwLowDateTime) // 10 == expected,
                    'OWNED_PROCESS_CREATION_TIME_CHANGED')
            require(kernel.TerminateProcess(handle, 0), 'OWNED_PROCESS_STOP_FAILED')
            require(kernel.WaitForSingleObject(handle, 10000) == 0, 'OWNED_PROCESS_DID_NOT_EXIT')
        finally:
            kernel.CloseHandle(handle)
        return 'stopped'

    def tools(self):
        values = {}
        properties = self.root / 'frontend/android/local.properties'
        require(properties.is_file(), 'ANDROID_LOCAL_SDK_PROPERTIES_MISSING')
        for line in properties.read_text().splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                values[key] = value.replace('\\\\', '\\').replace('\\:', ':')
        adb = Path(values.get('sdk.dir', '')) / 'platform-tools/adb.exe'
        require(adb.is_file(), 'ANDROID_ADB_MISSING')
        return adb

    def discovery_health(self, identity, lan):
        from lan_discovery import private, load_trust, probe_tls
        mode = getattr(self, 'mode', 'Full')
        folder = private(mode) / 'lan-discovery'
        if folder.exists():
            require(bool(lan), 'DISCOVERY_LAN_ADDRESS_REQUIRED')
            try:
                probe_tls(lan, load_trust(folder, mode, identity['identity']))
            except (OSError, ValueError):
                raise Blocked('DISCOVERY_TLS_NOT_READY') from None

    def install(self, serial, lan, logs, *, local_identity=None):
        adb = self.tools()
        apk = self.root / 'frontend/build/app/outputs/flutter-apk/app-debug.apk'
        # Reuse the existing guarded build/install implementation; no reverse in LAN mode.
        # Explicit process-only policy for this repository-local child script.
        # MachinePolicy/UserPolicy (Group Policy) still take precedence; never
        # change persistent settings, elevate or retry around an enforced denial.
        arguments = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', self.root / 'scripts' / 'install-fyp-android.ps1',
            '-Serial', serial, '-LanIp', lan, '-PublicApiUrl',
            'http://' + lan + ':8000' if local_identity is not None else PUBLIC]
        if local_identity is not None:
            require(getattr(self,'mode','Full') == 'Local', 'LOCAL_INSTALL_REQUIRES_LOCAL_HOST')
            arguments += ['-Mode','Local','-ExpectedIdentity',local_identity]
        result = self.command(arguments, timeout=900)
        (logs / 'android-install.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode != 0:
            output = result.stdout + result.stderr
            code = ('ANDROID_CHILD_SCRIPT_POLICY_REJECTED_ADMIN_REVIEW_REQUIRED'
                if 'running scripts is disabled' in output.lower() or 'PSSecurityException' in output
                else 'ANDROID_SIGNING_CERTIFICATE_CONFLICT_NO_UNINSTALL' if 'INSTALL_FAILED_UPDATE_INCOMPATIBLE' in output
                else 'ANDROID_VERSION_DOWNGRADE_REJECTED_NO_CLEAR' if 'INSTALL_FAILED_VERSION_DOWNGRADE' in output
                else 'ANDROID_BUILD_OR_INSTALL_FAILED_NO_UNINSTALL_NO_CLEAR')
            raise Blocked(code + ' — log: ' + str(logs / 'android-install.log'))
        installed = self.command([adb, '-s', serial, 'shell', 'pm', 'path', 'com.example.frontend'])
        require(installed.returncode == 0 and installed.stdout.startswith('package:'), 'INSTALLED_PACKAGE_NOT_FOUND')
        # Pull the actually installed base APK and compare full bytes, not just package/version.
        remote = installed.stdout.splitlines()[0].removeprefix('package:').strip()
        pulled = logs / 'installed-verification.apk'
        result = self.command([adb, '-s', serial, 'pull', remote, pulled], timeout=60)
        require(result.returncode == 0 and pulled.is_file(), 'INSTALLED_APK_VERIFICATION_FAILED')
        expected = hashlib.sha256(apk.read_bytes()).hexdigest()
        require(hashlib.sha256(pulled.read_bytes()).hexdigest() == expected, 'INSTALLED_APK_HASH_MISMATCH')
        pulled.unlink()
        return expected


class LocalHost(Host):
    mode = 'Local'

    @property
    def db_port(self):
        return self.profile()['db_port']

    def listeners(self):
        port=self.db_port
        return objects(self.ps('Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | '
            'Where-Object { $_.LocalPort -in 3306,8000,8003,8004,8005,'+str(port)+' } | '
            'Select-Object LocalAddress,LocalPort,OwningProcess | ConvertTo-Json -Compress'))

    def profile(self):
        from local_fyp import load_profile,private,LocalError
        try:
            return load_profile(private(self.root)/'settings.json')
        except LocalError as exc:
            raise Blocked(str(exc)) from None

    def guard(self):
        require(self.python.is_file(), 'BACKEND_VENV_MISSING')
        top=self.command(['git','rev-parse','--show-toplevel'])
        require(top.returncode==0 and canonical_path(top.stdout.strip())==canonical_path(self.root.resolve()),'WRONG_REPOSITORY')
        branch=self.command(['git','branch','--show-current'])
        require(branch.returncode==0 and bool(branch.stdout.strip()),'LOCAL_NAMED_BRANCH_REQUIRED')

    def database(self):
        from local_fyp import probe,private,LocalError
        try:
            return probe(profile=self.profile(),folder=private(self.root),prompt=input)
        except LocalError as exc:
            raise Blocked(str(exc)) from None

    def db_start(self, logs, prompt):
        raise Blocked('LOCAL_DATABASE_NOT_RUNNING_START_MYSQL_OR_MARIADB_MANUALLY')

    def http(self,path,*,public=False,gateway=False,lan=None):
        require(not public and not gateway,'LOCAL_MODE_NEVER_USES_CLOUDFLARE')
        return super().http(path,lan=lan)

    def prepare_admin(self,prompt):
        from local_fyp import private
        from admin_testing_launcher import initialize_admin
        folder=private(self.root);path=folder/'panel-admin.json'
        if not path.exists():
            require(prompt('Create your OWN Local panel credentials now? Type ADMIN: ')=='ADMIN','LOCAL_ADMIN_SETUP_REQUIRED')
            folder.mkdir(parents=True,exist_ok=True)
            initialize_admin(path)

    def beacon_path(self):
        return self.root/'runtime/local/ble-beacon/BleProbe.exe'

    def source_beacon_path(self):
        configured=self.profile()['ble_executable']
        return Path(configured) if configured else self.root/'runtime/local/beacon-not-configured/BleProbe.exe'

    def beacon_locations(self):
        try:
            return [self.beacon_path(), self.source_beacon_path()]
        except Blocked:
            # Shutdown of owned prepared binaries does not need DB credentials.
            return [self.beacon_path()]


class Workflow:
    def __init__(self, host, runtime=None, prompt=input):
        self.host = host
        self.mode = getattr(host,'mode','Full')
        self.db_port = 3306
        self.roles = {k:v for k,v in PORTS.items() if self.mode=='Full' or k!='gateway'}
        self.runtime = runtime or host.root / ('runtime/local' if self.mode=='Local' else 'runtime')
        self.prompt = prompt
        self.state_path = self.runtime / 'owned-processes.json'
        self.state = read_json(self.state_path, {})
        require(isinstance(self.state, dict) and set(self.state) <= set(self.roles)|{'beacon'},
                'OWNED_PROCESS_STATE_INVALID_NO_ACTION')
        # Keep old Started lines out of quick-retry/clock-reset readiness checks.
        self.logs = self.runtime / 'logs' / (time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
        self.logs.mkdir(parents=True, exist_ok=True)
        self.stage = 'Preflight'

    def args(self, role, beacon=None):
        if role == 'beacon':
            return [str(beacon), '--continuous']
        script = 'public_gateway.py' if role == 'gateway' else ('local_fyp.py' if self.mode=='Local' else 'original_fyp.py')
        args = [str(self.host.python), str(self.host.root / 'backend' / script)]
        if role != 'gateway':
            args += ['serve-panel' if role == 'admin' else 'serve-backend']
        if role == 'backend':
            args += ['--lan'] + (['--local-demo-slot2'] if self.mode=='Full' else [])
        return args

    def beacon_locations(self):
        # Fake hosts in offline tests may expose only their synthetic known path.
        return self.host.beacon_locations() if hasattr(self.host, 'beacon_locations') else [self.host.beacon_path()]

    def inventory(self):
        listeners = self.host.listeners()
        require(self.mode!='Local' or not any(r['LocalPort']==8004 for r in listeners),
                'LOCAL_MODE_PUBLIC_GATEWAY_PRESENT_STOP_FULL_OWNER_FIRST')
        processes = self.host.processes()
        # TLS discovery shares the verified backend PID, never a separate adopted process.
        backend_owners = {r['OwningProcess'] for r in listeners if r['LocalPort'] == 8000}
        for tls in [r for r in listeners if r['LocalPort'] == 8005]:
            require(tls['OwningProcess'] in backend_owners
                and tls['LocalAddress'] != '0.0.0.0', 'DISCOVERY_PORT_IDENTITY_CONFLICT')
        for role, port in self.roles.items():
            rows = [r for r in listeners if r['LocalPort'] == port]
            owners = {r['OwningProcess'] for r in rows}
            require(len(owners) <= 1, f'DUPLICATE_{role.upper()}_LISTENERS_NO_PROCESSES_CHANGED')
            if owners:
                row = next((p for p in processes if p['ProcessId'] in owners), None)
                require(matches(row, self.args(role), self.host.images), f'{role.upper()}_PORT_IDENTITY_CONFLICT')
                allowed = ('0.0.0.0',) if role == 'backend' else ('127.0.0.1',)
                require(all(r['LocalAddress'] in allowed for r in rows), f'{role.upper()}_BINDING_CONFLICT')
            # Collapse only normal venv wrapper/child pairs, not unrelated duplicates.
            same = [p for p in processes if matches(p, self.args(role), self.host.images)]
            pids = {p['ProcessId'] for p in same}
            roots = [p for p in same if p.get('ParentProcessId') not in pids]
            require(len(roots) <= 1, f'DUPLICATE_{role.upper()}_PROCESSES')
            require(not same or owners, f'{role.upper()}_RUNNING_WITHOUT_LISTENER')
        return listeners

    def wait(self, check, role, seconds=60):
        deadline = time.monotonic() + seconds
        while True:
            try:
                if check():
                    return
            except BeaconExited:
                raise
            except (httpx.HTTPError, Blocked, ValueError):
                pass
            require(time.monotonic() < deadline, role.upper() + '_READINESS_TIMEOUT')
            time.sleep(.4)

    def remember(self, role, row, args, images):
        initial=dict(args=args, images=images, processes=[])
        if self.mode=='Local':
            initial['mode']='Local'
        entry = self.state.setdefault(role, initial)
        require(entry.get('mode','Full')==self.mode,'OWNED_ROLE_MODE_CONFLICT')
        if self.mode=='Local':
            entry['mode']='Local'
        require(entry['args'] == args and entry['images'] == images, 'OWNED_ROLE_STATE_CONFLICT')
        value = record(row)
        if value not in entry['processes']:
            entry['processes'].append(value)
        save_json(self.state_path, self.state)

    def ensure(self, role, check):
        owners = [r for r in self.host.listeners() if r['LocalPort'] == PORTS[role]]
        if owners:
            require(check(), role.upper() + '_EXISTING_NOT_HEALTHY')
            return
        args = self.args(role)
        child, row = self.host.launch(args, role, self.logs)
        self.remember(role, row, args, self.host.images)
        self.wait(check, role)
        for owner in {r['OwningProcess'] for r in self.host.listeners() if r['LocalPort'] == PORTS[role]}:
            live = next((p for p in self.host.processes() if p['ProcessId'] == owner), None)
            require(live and (owner == child.pid or live.get('ParentProcessId') == child.pid)
                    and matches(live, args, self.host.images), 'NEW_LISTENER_NOT_OWNED')
            self.remember(role, live, args, self.host.images)

    def backend_health(self, lan=None):
        status, identity = self.host.http('/local-fyp/identity')
        ensure_identity(identity,self.mode)
        require(status == 200 and identity == self.identity, 'BACKEND_PINNED_IDENTITY_MISMATCH')
        status, config = self.host.http('/config', lan=lan)
        require(status == 200 and config.get('network_ble_test_mode') is False, 'DIAGNOSTIC_MODE_NOT_OFF')
        self.backend_config = {k:v for k,v in config.items() if k != 'server_time'}
        if hasattr(self.host, 'discovery_health'):
            self.host.discovery_health(identity, lan)
        return True

    def gateway_health(self, public=False):
        status, config = self.host.http('/config', gateway=not public, public=public)
        require(status == 200 and config.get('network_ble_test_mode') is False, 'GATEWAY_CONFIG_NOT_READY')
        require({k:v for k,v in config.items() if k != 'server_time'} == self.backend_config,
                'PUBLIC_AND_ORIGINAL_CONFIG_MISMATCH')
        for path, expected in (('/me', 401), ('/docs', 404), ('/attendance/start', 404),
            ('/local-fyp/identity', 404), ('/api/v1/devices', 404),
            ('/api/v1/network-ble-tests/start', 404), ('/verify-face', 404), ('/sessions', 404)):
            status, value = self.host.http(path, gateway=not public, public=public)
            require(status == expected and (expected != 404 or value.get('code') == 'PUBLIC_ROUTE_NOT_AVAILABLE'),
                    'PUBLIC_SECURITY_CHECK_FAILED')
        return True

    def start(self):
        self.host.guard()
        self.db_port = getattr(self.host,'db_port',3306)
        self.lan = self.host.lan()
        self.inventory()  # Detect conflicts before launching anything.
        database_label = 'Database' if self.mode=='Local' else 'MariaDB'
        self.stage = database_label
        if not any(r['LocalPort'] == self.db_port for r in self.host.listeners()):
            self.host.db_start(self.logs, self.prompt)
            self.wait(lambda: any(r['LocalPort'] == self.db_port for r in self.host.listeners()), database_label)
        self.identity = self.host.database()
        ensure_identity(self.identity,self.mode)
        if self.mode=='Full':
            self.stage = 'Cloudflare'
            self.host.cloudflare(self.runtime, self.prompt)
        self.stage = 'FastAPI'
        self.ensure('backend', lambda: self.backend_health(self.lan))
        self.stage = 'Admin'
        if self.mode=='Local':
            self.host.prepare_admin(self.prompt)
        self.ensure('admin', self.host.admin)
        if self.mode=='Full':
            self.stage = 'Public Gateway'
            self.ensure('gateway', self.gateway_health)
            self.gateway_health(public=True)
        self.beacon_status='READY'
        try:
            self.start_beacon()
        except Blocked as exc:
            if self.mode=='Full':
                raise
            self.beacon_status='NOT READY (optional): '+str(exc)
            (self.logs/'beacon-status.log').write_text(self.beacon_status)
        require(self.host.lan() == self.lan, 'WIFI_CHANGED_DURING_START_RETRY')
        self.inventory()
        if self.mode=='Local':
            print('Mode: LOCAL\nDatabase: READY\nFastAPI: READY\nAdmin: READY\nPublic Gateway: NOT USED\nCloudflare: NOT USED')
            print('BLE Beacon: '+self.beacon_status+'\nLaptop LAN IP: '+self.lan+
                  '\nGeneral/Classroom URL: http://'+self.lan+':8000\nDiagnostic Mode: OFF\nLogs: '+str(self.logs))
            return
        self.full_dashboard()

    def start_beacon(self):
        self.stage = 'BLE Beacon'
        rows = [(r,p) for r in self.host.processes() for p in self.beacon_locations()
                if matches(r, self.args('beacon', p), [str(p)])]
        require(len(rows) <= 1, 'DUPLICATE_BLE_BROADCASTERS')
        if rows:
            existing, beacon = rows[0]
            self.host.verify_beacon(beacon)
            args = self.args('beacon', beacon)
            stored = self.state.get('beacon', {})
            log = Path(stored.get('log', ''))
            confirmed = (record(existing) in stored.get('processes', []) and log.is_file()
                         and 'Started: advertising ' + BEACON_UUID in log.read_text(errors='replace'))
            if not confirmed:
                require(self.prompt('Existing known SENGHIN process is running. Confirm fresh tablet detection; type DETECTED: ') == 'DETECTED',
                        'BLE_EXISTING_ADVERTISING_UNVERIFIED')
        else:
            beacon = self.host.beacon()
            args = self.args('beacon', beacon)
            child, row = self.host.launch(args, 'beacon', self.logs)
            self.remember('beacon', row, args, [str(beacon)])
            log = self.logs / 'beacon.out.log'
            self.state['beacon']['log'] = str(log)
            save_json(self.state_path, self.state)
            def started():
                if child.poll() is not None or self.host.process(child.pid) is None:
                    raise BeaconExited(f'BLE_PROCESS_EXITED exit_code={child.poll()}; log: {self.logs / "beacon.err.log"}')
                return log.exists() and 'Started: advertising ' + BEACON_UUID in log.read_text(errors='replace')
            self.wait(started, 'BLE', seconds=15)
        require(self.host.lan() == self.lan, 'WIFI_CHANGED_DURING_START_RETRY')
        require(any(matches(r, args, [str(beacon)]) for r in self.host.processes()), 'BLE_PROCESS_EXITED')
        self.inventory()  # Recheck expected bindings and duplicate ownership after launch.

    def full_dashboard(self):
        for name in ('MariaDB', 'FastAPI', 'Admin', 'Public Gateway', 'Cloudflare', 'BLE Beacon'):
            print(name + ': READY')
        print('Laptop LAN IP: ' + self.lan + '\nPublic URL: ' + PUBLIC +
              '\nClassroom URL: http://' + self.lan + ':8000\nDiagnostic Mode: OFF')
        print('Logs: ' + str(self.logs))

    def stop(self):
        self.host.guard()
        failures = []
        for role in ('gateway', 'admin', 'backend', 'beacon'):
            entry = self.state.get(role)
            if not entry:
                print(role + ': preserved/not launched by this workflow')
                continue
            if entry.get('mode','Full')!=self.mode:
                failures.append(role)
                print(role+': NOT STOPPED; owned by another mode')
                continue
            options = [(self.args(role,p), [str(p)]) for p in self.beacon_locations()] if role == 'beacon' else [(self.args(role), self.host.images)]
            if not any(entry.get('args') == args and entry.get('images') == images for args,images in options):
                failures.append(role)
                print(role + ': NOT STOPPED; unexpected stored command')
                continue
            remaining = []
            for process in reversed(entry['processes']):
                try:
                    print(role + ': ' + self.host.stop(process, entry['args'], entry['images']))
                except Blocked:
                    remaining.append(process)
                    failures.append(role)
                    print(role + ': NOT STOPPED; process identity changed or unreadable')
            if remaining:
                entry['processes'] = list(reversed(remaining))
            else:
                self.state.pop(role)
            save_json(self.state_path, self.state)
        print(('Database' if self.mode=='Local' else 'MariaDB') + ': PRESERVED\nCloudflared Windows service: PRESERVED')
        require(not failures, 'SOME_OWNED_PROCESSES_COULD_NOT_BE_VERIFIED_NO_UNSAFE_STOP')

    def install(self, serial=None):
        self.stage = 'Android install'
        self.host.guard()
        self.lan = self.host.lan()
        listeners = self.inventory()
        for role, port in self.roles.items():
            require(any(r['LocalPort'] == port for r in listeners), role.upper() + '_NOT_RUNNING_RUN_FYP_START')
        self.identity = self.host.database()
        ensure_identity(self.identity,self.mode)
        self.backend_health(self.lan)
        if self.mode=='Full':
            self.gateway_health()
            self.gateway_health(public=True)
        adb = self.host.tools()
        devices = self.host.command([adb, 'devices', '-l'])
        require(devices.returncode == 0, 'ADB_DEVICE_LIST_FAILED')
        print(devices.stdout)  # Serial/model only; never credentials.
        selected = choose_device(devices.stdout, serial, self.prompt)
        if self.mode=='Local':
            print('LOCAL APK uses your Local database, not Full mode. Existing app data/keys are preserved; sessions and device registration may be incompatible. No records will be copied.')
            require(self.prompt('Confirm this intentional environment switch/install; type LOCAL: ')=='LOCAL','LOCAL_ANDROID_ENVIRONMENT_SWITCH_NOT_CONFIRMED')
            digest=self.host.install(selected,self.lan,self.logs,local_identity=self.identity['identity'])
        else:
            digest = self.host.install(selected, self.lan, self.logs)
        print('Android: INSTALLED AND VERIFIED\nSerial: ' + selected + '\nAPK SHA-256: ' + digest +
              '\nMode: '+self.mode+'\nGeneral URL: '+('http://'+self.lan+':8000' if self.mode=='Local' else PUBLIC)+ '\nClassroom URL: http://' + self.lan + ':8000')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'install', 'stop'))
    parser.add_argument('--serial')
    parser.add_argument('--mode',choices=('Full','Local'),default='Full')
    args = parser.parse_args(argv)
    flow = None
    try:
        host = LocalHost() if args.mode=='Local' else Host()
        host.guard()
        flow = Workflow(host)
        # Both modes contend for the same ports, so share the lifecycle lock,
        # while ownership state/logs remain separate. No process is adopted.
        with lifecycle_lock(host.root/'runtime'):
            if args.action == 'install':
                flow.install(args.serial)
            else:
                getattr(flow, args.action)()
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        # Driver/Cloudflare errors may contain secrets: controlled codes only.
        code = str(exc) if isinstance(exc, Blocked) else type(exc).__name__
        message = ('Preflight: NOT READY — ' + code) if flow is None else (
            f'{flow.stage}: NOT READY — {code}\nFailure log: {flow.logs / "workflow.log"}\nComponent logs: {flow.logs}')
        if flow is not None:
            (flow.logs / 'workflow.log').write_text(message, encoding='utf-8')
        print(message)
        print('No unknown process was stopped. fyp-stop.ps1 can clean up verified owned processes.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
