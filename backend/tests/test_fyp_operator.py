"""Three-command orchestration with disposable state and mocked OS/HTTP effects.

No original service start/stop, database queries or APK installs occur here.
"""
import base64
import json
from pathlib import Path
import secrets
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fyp_operator import (Blocked, Host, Workflow, choose_device, token_tunnel,
    ensure_identity, save_json, TUNNEL_NAME, BEACON_UUID)
from disposable_processes import record, matches


IDENTITY = dict(environment='original', db_port=3306,
                database='attendance_proposal_xampp', identity='a' * 64)


class FakeHost:
    root = Path(r'C:\FYP\FYP-Biometric-Attendance-System')
    python = root / 'backend/venv/Scripts/python.exe'
    images = [str(python)]
    def __init__(self):
        self.rows = []
        self.ports = []
        self.events = []
        self.address = '192.0.2.8'
        self.identity = IDENTITY.copy()
        self.beacon_missing = False
        self.diagnostic = False
        self.device_list = 'List of devices attached\n7732690b device model:synthetic\n'
        self.next_pid = 100
    def guard(self):
        self.events.append('guard')
    def lan(self):
        return self.address
    def listeners(self):
        return self.ports.copy()
    def processes(self):
        return self.rows.copy()
    def process(self, pid):
        return next((r for r in self.rows if r['ProcessId'] == pid), None)
    def database(self):
        self.events.append('database_read')
        return self.identity
    def db_start(self, logs, prompt):
        if prompt('START database?') != 'START':
            raise Blocked('MARIADB_START_NOT_CONFIRMED')
        self.events.append('db_start')
        self.ports.append(dict(LocalPort=3306, LocalAddress='127.0.0.1', OwningProcess=1))
    def cloudflare(self, runtime, prompt):
        self.events.append('cloudflare_verify')
    def http(self, path, *, public=False, gateway=False, lan=None):
        self.events.append(('http', path, public, gateway, lan))
        if path == '/local-fyp/identity' and not (public or gateway):
            return 200, self.identity
        if path == '/config':
            return 200, {'network_ble_test_mode':self.diagnostic}
        if path == '/me':
            return 401, {'message':'Sign in'}
        return 404, {'code':'PUBLIC_ROUTE_NOT_AVAILABLE'}
    def admin(self):
        return True
    def beacon_path(self):
        return Path(r'C:\known\BleProbe.exe')
    def beacon(self):
        if self.beacon_missing:
            raise Blocked('BLE_KNOWN_EXECUTABLE_MISSING')
        return self.beacon_path()
    def verify_beacon(self, path):
        pass
    def launch(self, args, role, logs):
        self.next_pid += 1
        row = dict(ProcessId=self.next_pid, ParentProcessId=0, ExecutablePath=args[0],
            CommandLine=subprocess.list2cmdline(args), created_at='2026-11-16T00:00:00+00:00')
        self.rows.append(row)
        self.events.append(('launch', role))
        if role != 'beacon':
            self.ports.append(dict(LocalPort={'backend':8000,'admin':8003,'gateway':8004}[role],
                LocalAddress='0.0.0.0' if role=='backend' else '127.0.0.1', OwningProcess=row['ProcessId']))
        else:
            (logs / 'beacon.out.log').write_text('Started: advertising ' + BEACON_UUID)
        return SimpleNamespace(pid=row['ProcessId'], poll=lambda:None), row
    def stop(self, stored, args, images):
        row = self.process(stored['pid'])
        if row is None:
            return 'already exited'
        if record(row) != stored or not matches(row, args, images):
            raise Blocked('IDENTITY_CHANGED')
        self.events.append(('stop', row['ProcessId']))
        self.rows.remove(row)
        self.ports = [p for p in self.ports if p['OwningProcess'] != row['ProcessId']]
        return 'stopped'
    def tools(self):
        return Path('synthetic-adb.exe')
    def command(self, args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=self.device_list)
    def install(self, serial, lan, logs):
        self.events.append(('install', serial, lan))
        return 'synthetic-apk-hash'


def workflow(tmp_path, host=None, answer='START'):
    return Workflow(host or FakeHost(), tmp_path / 'runtime', prompt=lambda _:answer)


def test_cold_start_order_and_stop_preserves_shared_services(tmp_path):
    f=workflow(tmp_path)
    f.start()
    events=f.host.events
    assert events.index('db_start') < events.index('database_read')
    assert events.index('database_read') < events.index(('launch','backend'))
    assert events.index(('launch','backend')) < events.index(('launch','admin')) < events.index(('launch','gateway'))
    state=json.loads(f.state_path.read_text())
    assert set(state)=={'backend','admin','gateway','beacon'}
    f.stop()
    assert json.loads(f.state_path.read_text()) == {}
    assert [r['LocalPort'] for r in f.host.listeners()] == [3306]


def test_healthy_services_reused_never_adopted_for_shutdown(tmp_path):
    first=workflow(tmp_path / 'owner')
    first.start()
    other=workflow(tmp_path / 'different-owner', first.host, answer='DETECTED')
    before=len([e for e in first.host.events if isinstance(e,tuple) and e[0]=='launch'])
    other.start()
    assert not other.state
    other.stop()
    assert not any(isinstance(e,tuple) and e[0]=='stop' for e in first.host.events)
    assert len([e for e in first.host.events if isinstance(e,tuple) and e[0]=='launch']) == before


def test_duplicate_backends_block_before_any_new_launch(tmp_path):
    f=workflow(tmp_path)
    f.host.ports=[dict(LocalPort=8000,LocalAddress='127.0.0.1',OwningProcess=2),
                  dict(LocalPort=8000,LocalAddress='0.0.0.0',OwningProcess=3)]
    with pytest.raises(Blocked,match='DUPLICATE_BACKEND'):
        f.start()
    assert 'db_start' not in f.host.events
    assert not any(isinstance(e,tuple) and e[0]=='launch' for e in f.host.events)


def test_wrong_database_never_launches_backend_or_gateway(tmp_path):
    f=workflow(tmp_path)
    f.host.identity['database']='wrong'
    with pytest.raises(Blocked,match='DATABASE_IDENTITY'):
        f.start()
    assert not f.state


def test_database_start_requires_confirmation_and_no_database_ownership(tmp_path):
    f=workflow(tmp_path,answer='NO')
    with pytest.raises(Blocked,match='NOT_CONFIRMED'):
        f.start()
    assert not f.state
    assert 'db_start' not in f.host.events


def test_missing_beacon_reports_failure_without_substitution(tmp_path):
    f=workflow(tmp_path)
    f.host.beacon_missing=True
    with pytest.raises(Blocked,match='BLE_KNOWN_EXECUTABLE_MISSING'):
        f.start()
    assert 'beacon' not in f.state
    f.stop()  # Partial launch remains safely recoverable.


def test_changing_lan_ip_used_for_install_and_explicit_device_selection(tmp_path):
    f=workflow(tmp_path)
    f.start()
    f.host.address='198.51.100.42'
    f.install()
    assert ('install','7732690b','198.51.100.42') in f.host.events
    assert ('http','/config',False,False,'198.51.100.42') in f.host.events


def test_device_selection_does_not_choose_other_or_ambiguous_device():
    listing='List of devices attached\n7732690b device\nOTHER device\n'
    assert choose_device(listing,prompt=lambda _:'OTHER')=='OTHER'
    with pytest.raises(Blocked):
        choose_device(listing,prompt=lambda _:'')
    with pytest.raises(Blocked):
        choose_device('List of devices attached\nOTHER unauthorized\n')
    with pytest.raises(Blocked):
        choose_device(listing,serial='MISSING')
    assert choose_device('List of devices attached\nOTHER device\n',prompt=lambda _:'OTHER')=='OTHER'


def test_missing_adb_stops_before_install(tmp_path):
    root=tmp_path / 'repo'
    (root / 'frontend/android').mkdir(parents=True)
    (root / 'frontend/android/local.properties').write_text('sdk.dir=C:\\missing-sdk')
    with pytest.raises(Blocked,match='ADB_MISSING'):
        Host(root).tools()


def test_recycled_pid_never_stopped_and_state_retained(tmp_path):
    f=workflow(tmp_path)
    f.start()
    original=f.state['backend']['processes'][0]
    row=f.host.process(original['pid'])
    row['created_at']='2026-11-17T00:00:00+00:00'
    with pytest.raises(Blocked,match='COULD_NOT_BE_VERIFIED'):
        f.stop()
    assert not ('stop',original['pid']) in f.host.events
    assert f.host.process(original['pid']) is not None
    assert 'backend' in f.state


def test_tampered_stored_command_cannot_stop_unrelated_program(tmp_path):
    f=workflow(tmp_path)
    f.state={'backend':dict(args=['notepad.exe'], images=['notepad.exe'], processes=[dict(pid=999)])}
    with pytest.raises(Blocked):
        f.stop()
    assert not any(isinstance(e,tuple) and e[0]=='stop' for e in f.host.events)


def test_diagnostic_mode_true_refuses_existing_backend(tmp_path):
    f=workflow(tmp_path)
    f.host.diagnostic=True
    # Avoid waiting: existing unhealthy listener is rejected immediately.
    f.host.launch(f.args('backend'),'backend',f.logs)
    with pytest.raises(Blocked,match='DIAGNOSTIC_MODE_NOT_OFF'):
        f.start()
    assert 'gateway' not in f.state


def test_cloudflare_token_is_not_saved_and_mapping_changes_rejected(tmp_path,monkeypatch):
    h=Host()
    tunnel='00000000-0000-0000-0000-000000000001'
    secret=secrets.token_urlsafe(24)
    token=base64.urlsafe_b64encode(json.dumps({'t':tunnel,'s':secret}).encode()).decode()
    monkeypatch.setattr(h,'ps',lambda _:dict(State='Running',ProcessId=4,
        PathName=subprocess.list2cmdline([r'C:\cloudflared.exe','tunnel','run','--token',token])))
    h.cloudflare(tmp_path,lambda _:'CONFIRM')
    data=(tmp_path / 'approved-tunnel.json').read_text()
    assert secret not in data and token not in data
    assert json.loads(data)==dict(name=TUNNEL_NAME,tunnel_id=tunnel)
    h.cloudflare(tmp_path,lambda _:pytest.fail('Confirmed mapping should not prompt again'))
    save_json(tmp_path / 'approved-tunnel.json',dict(name=TUNNEL_NAME,tunnel_id='different'))
    with pytest.raises(Blocked,match='ID_CHANGED'):
        h.cloudflare(tmp_path,lambda _:'CONFIRM')


def test_native_stop_rejects_wrong_creation_time_before_any_windows_termination(monkeypatch):
    h=Host()
    args=[str(h.python),'expected.py']
    row=dict(ProcessId=123,ExecutablePath=str(h.python),CommandLine=subprocess.list2cmdline(args),
             created_at='2026-11-16T00:00:00+00:00')
    stored=record(row)
    monkeypatch.setattr(h,'process',lambda _:dict(row,created_at='2026-11-17T00:00:00+00:00'))
    with pytest.raises(Blocked,match='IDENTITY_CHANGED'):
        h.stop(stored,args,h.images)


def test_wrong_listener_binding_never_reused(tmp_path):
    f=workflow(tmp_path)
    f.host.launch(f.args('gateway'),'gateway',f.logs)
    f.host.ports[0]['LocalAddress']='0.0.0.0'
    with pytest.raises(Blocked,match='GATEWAY_BINDING_CONFLICT'):
        f.start()
    assert 'db_start' not in f.host.events


def test_owned_venv_listener_child_recorded_separately(tmp_path):
    f=workflow(tmp_path)
    original_launch=f.host.launch
    def with_wrapper(args,role,logs):
        child,row=original_launch(args,role,logs)
        if role=='backend':
            listener=dict(row,ProcessId=500,ParentProcessId=row['ProcessId'])
            f.host.rows.append(listener)
            f.host.ports[-1]['OwningProcess']=500
        return child,row
    f.host.launch=with_wrapper
    f.start()
    assert len(f.state['backend']['processes'])==2
    f.stop()
    stopped=[e[1] for e in f.host.events if isinstance(e,tuple) and e[0]=='stop']
    assert stopped.index(500)<stopped.index(101)


def test_service_ownership_not_recorded_when_already_running(tmp_path):
    f=workflow(tmp_path)
    f.host.ports.append(dict(LocalPort=3306,LocalAddress='127.0.0.1',OwningProcess=900))
    f.start()
    assert 'db_start' not in f.host.events
    assert 'MariaDB' not in f.state and 'Cloudflare' not in f.state


def test_cloudflare_stopped_requires_manual_service_action_without_launch(tmp_path,monkeypatch):
    h=Host()
    monkeypatch.setattr(h,'ps',lambda _:dict(State='Stopped',ProcessId=0,PathName='not printed'))
    with pytest.raises(Blocked,match='SERVICE_NOT_RUNNING'):
        h.cloudflare(tmp_path,lambda _:pytest.fail('Should not prompt for service token or elevation'))


def test_host_launch_forces_diagnostic_off_and_hidden_logs(tmp_path,monkeypatch):
    import fyp_operator
    h=Host()
    row=dict(ProcessId=123,ExecutablePath=str(h.python),CommandLine='synthetic',created_at='synthetic')
    observed={}
    def launch(args,**kwargs):
        observed.update(kwargs)
        return SimpleNamespace(pid=123)
    monkeypatch.setenv('NETWORK_BLE_TEST_MODE','true')
    monkeypatch.setattr(fyp_operator.subprocess,'Popen',launch)
    monkeypatch.setattr(h,'process',lambda _:row)
    h.launch(['synthetic'],'backend',tmp_path)
    assert observed['env']['NETWORK_BLE_TEST_MODE']=='false'
    assert observed['env']['FYP_PUBLIC_HOST']=='api.bioattsys.xyz'
    assert observed['creationflags']==fyp_operator.QUIET


def test_public_config_mismatch_blocks_install_without_any_adb_action(tmp_path):
    f=workflow(tmp_path)
    f.start()
    normal=f.host.http
    def wrong(path,**kwargs):
        status,value=normal(path,**kwargs)
        if path=='/config' and kwargs.get('public'):
            value=dict(value,verification_seconds=999)
        return status,value
    f.host.http=wrong
    with pytest.raises(Blocked,match='CONFIG_MISMATCH'):
        f.install()
    assert not any(isinstance(e,tuple) and e[0]=='install' for e in f.host.events)


def test_protected_service_token_file_not_read_and_metadata_change_blocks(tmp_path,monkeypatch):
    token=tmp_path / 'protected-token'
    token.write_text(secrets.token_urlsafe(32))
    h=Host()
    command=subprocess.list2cmdline([r'C:\cloudflared.exe','tunnel','run','--token-file',str(token)])
    monkeypatch.setattr(h,'ps',lambda _:dict(State='Running',ProcessId=9,PathName=command))
    answers=iter(['00000000-0000-0000-0000-000000000001','CONFIRM'])
    h.cloudflare(tmp_path,lambda _:next(answers))
    approved=json.loads((tmp_path / 'approved-tunnel.json').read_text())
    assert approved['verification']=='operator-confirmed-protected-service'
    assert token.read_text() not in json.dumps(approved)
    h.cloudflare(tmp_path,lambda _:pytest.fail('Unchanged service binding must reuse approval'))
    token.write_text(secrets.token_urlsafe(64))
    with pytest.raises(Blocked,match='SERVICE_BINDING_CHANGED'):
        h.cloudflare(tmp_path,lambda _:'CONFIRM')


def test_token_file_parser_never_reads_protected_contents(monkeypatch):
    monkeypatch.setattr(Path,'read_text',lambda *_args,**_kwargs:pytest.fail('Must not read the token'))
    assert token_tunnel(['cloudflared.exe','tunnel','run','--token-file',r'C:\private-token']) is None


def test_readiness_failure_has_bounded_deadline(tmp_path,monkeypatch):
    import fyp_operator
    f=workflow(tmp_path)
    samples=iter([0.0,61.0])
    monkeypatch.setattr(fyp_operator.time,'monotonic',lambda:next(samples))
    with pytest.raises(Blocked,match='BACKEND_READINESS_TIMEOUT'):
        f.wait(lambda:False,'backend',seconds=60)


def test_install_signature_failure_reports_no_destructive_recovery(tmp_path,monkeypatch):
    h=Host()
    monkeypatch.setattr(h,'tools',lambda:Path('synthetic-adb.exe'))
    calls=[]
    def failed(args,**kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1,stdout='',stderr='Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE]')
    monkeypatch.setattr(h,'command',failed)
    with pytest.raises(Blocked,match='SIGNING_CERTIFICATE_CONFLICT_NO_UNINSTALL'):
        h.install('7732690b','192.0.2.9',tmp_path)
    assert len(calls)==1
    assert not any('uninstall' in str(arg) or arg=='clear' for arg in calls[0])


def test_install_before_start_is_actionable_and_never_builds_or_installs(tmp_path):
    f=workflow(tmp_path)
    with pytest.raises(Blocked,match='BACKEND_NOT_RUNNING_RUN_FYP_START'):
        f.install()
    assert 'database_read' not in f.host.events
    assert not any(isinstance(e,tuple) and e[0]=='install' for e in f.host.events)


def test_nested_installer_process_policy_handles_exact_disabled_scripts_failure(tmp_path,monkeypatch):
    import hashlib
    h=Host(tmp_path)
    apk=tmp_path/'frontend/build/app/outputs/flutter-apk/app-debug.apk'
    apk.parent.mkdir(parents=True)
    apk.write_bytes(b'synthetic-apk-no-device-install')
    monkeypatch.setattr(h,'tools',lambda:Path('synthetic-adb.exe'))
    calls=[]
    def command(args,**kwargs):
        calls.append(args)
        if args[0]=='powershell.exe':
            if args[1:6] != ['-NoProfile','-ExecutionPolicy','Bypass','-File',tmp_path/'install-fyp-android.ps1']:
                return SimpleNamespace(returncode=1,stdout='',stderr=
                    'install-fyp-android.ps1 cannot be loaded because running scripts is disabled on this system.')
            assert args[args.index('-Serial')+1]=='7732690b'
            assert args[args.index('-LanIp')+1]=='192.0.2.9'
            assert args[args.index('-PublicApiUrl')+1]=='https://api.bioattsys.xyz'
            return SimpleNamespace(returncode=0,stdout='Synthetic build/install success',stderr='')
        if 'pull' in args:
            Path(args[-1]).write_bytes(apk.read_bytes())
            return SimpleNamespace(returncode=0,stdout='',stderr='')
        return SimpleNamespace(returncode=0,stdout='package:/synthetic/base.apk\n',stderr='')
    monkeypatch.setattr(h,'command',command)
    assert h.install('7732690b','192.0.2.9',tmp_path)==hashlib.sha256(apk.read_bytes()).hexdigest()
    assert len(calls)==3
    assert not any('Set-ExecutionPolicy' in str(arg) for call in calls for arg in call)


def test_enforced_child_policy_failure_stops_without_retry_or_device_commands(tmp_path,monkeypatch):
    h=Host()
    monkeypatch.setattr(h,'tools',lambda:Path('synthetic-adb.exe'))
    calls=[]
    def denied(args,**kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1,stdout='',stderr=
            'PSSecurityException: running scripts is disabled on this system.')
    monkeypatch.setattr(h,'command',denied)
    with pytest.raises(Blocked,match='CHILD_SCRIPT_POLICY_REJECTED_ADMIN_REVIEW_REQUIRED'):
        h.install('7732690b','192.0.2.9',tmp_path)
    assert len(calls)==1
    assert calls[0][0]=='powershell.exe'
