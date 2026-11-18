"""Local/Full isolation using synthetic OS fixtures and in-memory SQLite only."""
import json
from pathlib import Path
import secrets
import sys

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, inspect, text

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fyp_operator import Workflow,LocalHost,Blocked,Host,PUBLIC
from local_fyp import load_profile,settings,initialize_empty,LocalError
from test_fyp_operator import FakeHost, IDENTITY


class LocalFake(FakeHost):
    mode='Local'
    db_port=3306
    def __init__(self):
        super().__init__()
        self.address='192.168.10.20'
        self.identity=dict(IDENTITY,environment='partner_local',database='partner_test')
        self.ports=[dict(LocalPort=3306,LocalAddress='127.0.0.1',OwningProcess=1)]
    def cloudflare(self,*args):
        pytest.fail('Local must not inspect/require Cloudflare')
    def http(self,path,**kwargs):
        assert not kwargs.get('public') and not kwargs.get('gateway')
        return super().http(path,**kwargs)
    def prepare_admin(self,prompt):
        self.events.append('own_admin_checked')
    def db_start(self,*args):
        raise Blocked('LOCAL_DATABASE_NOT_RUNNING_START_PARTNER_XAMPP_MANUALLY')
    def install(self,serial,lan,logs,**kwargs):
        assert kwargs['local_identity']==self.identity['identity']
        self.events.append(('local_install',serial,lan))
        return 'synthetic-local-apk'


def local_flow(tmp_path,host=None):
    return Workflow(host or LocalFake(),tmp_path/'runtime-local',prompt=lambda _:'LOCAL')


def test_local_start_without_cloudflare_or_gateway_and_optional_ble(tmp_path,capsys):
    f=local_flow(tmp_path)
    f.host.beacon_missing=True
    f.start()
    assert set(f.state)=={'backend','admin'}
    assert all(entry['mode']=='Local' for entry in f.state.values())
    assert 'cloudflare_verify' not in f.host.events
    output=capsys.readouterr().out
    assert 'Mode: LOCAL' in output and 'NOT READY (optional)' in output
    assert PUBLIC not in output
    assert f.args('backend')[-2:]==['serve-backend','--lan']
    assert 'local_fyp.py' in f.args('backend')[1]


def test_local_install_same_lan_uses_own_identity_and_requires_switch_confirmation(tmp_path):
    f=local_flow(tmp_path);f.start();f.install()
    assert ('local_install','7732690b','192.168.10.20') in f.host.events
    f.prompt=lambda _:'NO'
    with pytest.raises(Blocked,match='ENVIRONMENT_SWITCH_NOT_CONFIRMED'):
        f.install()


def test_local_does_not_touch_running_full_gateway(tmp_path):
    f=local_flow(tmp_path)
    f.host.ports.append(dict(LocalPort=8004,LocalAddress='127.0.0.1',OwningProcess=900))
    with pytest.raises(Blocked,match='PUBLIC_GATEWAY_PRESENT'):
        f.start()
    assert not f.state
    assert not any(isinstance(e,tuple) and e[0] in ('launch','stop') for e in f.host.events)


def test_local_never_uses_original_db_identity(tmp_path):
    f=local_flow(tmp_path);f.host.identity=IDENTITY.copy()
    with pytest.raises(Blocked,match='PARTNER_LOCAL_DATABASE_IDENTITY_MISMATCH'):
        f.start()
    assert not f.state


def test_missing_local_database_does_not_start_or_create_anything(tmp_path):
    f=local_flow(tmp_path);f.host.ports=[]
    with pytest.raises(Blocked,match='LOCAL_DATABASE_NOT_RUNNING'):
        f.start()
    assert f.host.events==['guard']


def test_local_stop_rejects_full_ownership_even_for_matching_pid(tmp_path):
    f=local_flow(tmp_path);f.start()
    f.state['backend']['mode']='Full'
    pid=f.state['backend']['processes'][0]['pid']
    with pytest.raises(Blocked,match='COULD_NOT_BE_VERIFIED'):
        f.stop()
    assert f.host.process(pid) is not None


def test_full_defaults_remain_same_and_state_directories_separate(tmp_path):
    full=Workflow(FakeHost(),tmp_path/'full',prompt=lambda _:'START')
    local=local_flow(tmp_path)
    assert full.mode=='Full' and full.roles.keys()=={'backend','admin','gateway'}
    assert full.args('backend')[-2:]==['--lan','--local-demo-slot2']
    assert local.roles.keys()=={'backend','admin'}
    assert full.state_path != local.state_path


def valid_profile():
    return dict(db_host='127.0.0.1',db_port=3306,db_name='partner_test',db_user='partner_app',
        db_password=secrets.token_urlsafe(24),biometric_key=Fernet.generate_key().decode(),
        fyp_account_bound_enrollment=False,ble_executable='')


def test_private_profile_explicit_secrets_flags_and_original_schema_guard(tmp_path,monkeypatch):
    profile=valid_profile();path=tmp_path/'settings.json';path.write_text(json.dumps(profile))
    monkeypatch.setenv('NETWORK_BLE_TEST_MODE','true')
    value=settings(load_profile(path))
    assert value.db_name=='partner_test' and value.db_password==profile['db_password']
    assert value.network_ble_test_mode is False and value.demo_mode is False
    assert value.biometric_key==profile['biometric_key']
    profile['db_name']='attendance_proposal_xampp';path.write_text(json.dumps(profile))
    with pytest.raises(LocalError,match='ORIGINAL_FORBIDDEN'):
        load_profile(path)


def test_empty_initialization_uses_all_existing_tables_no_records_and_refuses_second_run():
    db=create_engine('sqlite://')
    initialize_empty(db)
    from application_schema import application_tables
    assert set(inspect(db).get_table_names())=={t.name for t in application_tables()}
    with db.connect() as c:
        for name in ('attendance','students','registered_devices','device_enrollment_revisions'):
            assert c.scalar(text('SELECT COUNT(*) FROM '+name))==0
    with pytest.raises(LocalError,match='NO_EXISTING_TABLES_CHANGED'):
        initialize_empty(db)
    db.dispose()


def test_local_http_adapter_cannot_call_public_even_accidentally():
    h=LocalHost()
    with pytest.raises(Blocked,match='NEVER_USES_CLOUDFLARE'):
        h.http('/config',public=True)


def test_local_installer_arguments_pin_both_urls_and_own_backend(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import hashlib
    host=LocalHost(tmp_path)
    monkeypatch.setattr(host,'tools',lambda:Path('synthetic-adb.exe'))
    apk=tmp_path/'frontend/build/app/outputs/flutter-apk/app-debug.apk'
    apk.parent.mkdir(parents=True);apk.write_bytes(b'synthetic-local-apk')
    seen=[]
    def command(args,**_):
        seen.append(args)
        if args[0]=='powershell.exe':
            assert args[args.index('-PublicApiUrl')+1]=='http://192.168.10.20:8000'
            assert args[args.index('-Mode')+1]=='Local'
            assert args[args.index('-ExpectedIdentity')+1]=='a'*64
            assert not any('bioattsys.xyz' in str(arg) for arg in args)
            return SimpleNamespace(returncode=0,stdout='',stderr='')
        if 'pull' in args:
            Path(args[-1]).write_bytes(apk.read_bytes())
        return SimpleNamespace(returncode=0,stdout='package:/synthetic/base.apk',stderr='')
    monkeypatch.setattr(host,'command',command)
    assert host.install('7732690b','192.168.10.20',tmp_path,local_identity='a'*64)==hashlib.sha256(apk.read_bytes()).hexdigest()
    assert len(seen)==3


def test_private_identity_pin_is_explicit_and_drift_cannot_overwrite(tmp_path,monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace
    import local_fyp,original_fyp
    own=valid_profile()
    actual=dict(port=3306,schema=own['db_name'],account='partner@localhost',datadir='own-data',
                basedir='own-xampp',version='10.4-MariaDB',encryption_key_sha256='a'*64)
    db=SimpleNamespace(connect=lambda:nullcontext(object()),dispose=lambda:None)
    monkeypatch.setattr(local_fyp,'engine',lambda _:db)
    monkeypatch.setattr(local_fyp,'database_identity',lambda *_:actual.copy())
    monkeypatch.setattr(original_fyp,'validate_schema',lambda _:None)
    with pytest.raises(LocalError,match='NOT_PINNED'):
        local_fyp.probe(profile=own,folder=tmp_path)
    identity=local_fyp.probe(profile=own,folder=tmp_path,prompt=lambda _:'PIN')
    assert identity['environment']=='partner_local'
    before=(tmp_path/'identity.json').read_bytes()
    assert own['db_password'].encode() not in before and own['biometric_key'].encode() not in before
    actual['datadir']='different-server'
    with pytest.raises(LocalError,match='PINNED_DATABASE_OR_POLICY_CHANGED'):
        local_fyp.probe(profile=own,folder=tmp_path,prompt=lambda _:'PIN')
    assert (tmp_path/'identity.json').read_bytes()==before


def test_local_guard_accepts_own_clone_and_never_requires_authors_absolute_path(tmp_path,monkeypatch):
    from types import SimpleNamespace
    (tmp_path/'backend/venv/Scripts').mkdir(parents=True)
    (tmp_path/'backend/venv/Scripts/python.exe').touch()
    h=LocalHost(tmp_path)
    monkeypatch.setattr(h,'command',lambda args:SimpleNamespace(returncode=0,
        stdout=str(tmp_path) if '--show-toplevel' in args else 'SH'))
    h.guard()
