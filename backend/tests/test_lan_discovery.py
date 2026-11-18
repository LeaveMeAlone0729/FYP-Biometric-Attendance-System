"""Synthetic certificates, mocked OS/advertising and ASGI only. No production SQL."""
import asyncio
import json
from pathlib import Path
import ssl
import sys
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lan_discovery as lan
from test_public_gateway import client as gateway_client
from test_fyp_operator import FakeHost, Workflow, Blocked


@pytest.fixture
def provisioned(tmp_path):
    folder = tmp_path / 'full'
    trust = lan.provision(folder, 'Full', 'a' * 64, protect=lambda _: None)
    return folder, trust


def test_explicit_new_identity_and_no_overwrite(provisioned):
    folder, trust = provisioned
    before = {p.name:p.read_bytes() for p in folder.iterdir()}
    with pytest.raises(FileExistsError):
        lan.provision(folder, 'Full', 'a' * 64, protect=lambda _:None)
    assert before == {p.name:p.read_bytes() for p in folder.iterdir()}
    assert 'PRIVATE' not in json.dumps(trust)
    assert trust == lan.load_trust(folder, 'Full', 'a' * 64)
    assert 'server.key' not in json.dumps(lan.identity_response(trust))


@pytest.mark.parametrize('mode,identity', [('Local','a'*64),('Full','b'*64)])
def test_wrong_environment_or_database_rejected(provisioned, mode, identity):
    with pytest.raises(ValueError, match='BINDING_MISMATCH'):
        lan.load_trust(provisioned[0], mode, identity)


@pytest.mark.parametrize('address', ['127.0.0.1','0.0.0.0','8.8.8.8','169.254.1.3','::1','224.0.0.251'])
def test_unrelated_network_addresses_rejected(address):
    with pytest.raises(ValueError):
        lan.private_ip(address)


@pytest.mark.parametrize('address', ['192.168.0.162','10.46.58.220','172.16.2.8'])
def test_private_wifi_hint(address):
    assert lan.private_ip(address) == address  # eligibility, never identity/authorization


def test_tls_config_loads_private_ca_and_key(provisioned):
    folder, trust = provisioned
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(folder/'server.pem', folder/'server.key')
    client = ssl.create_default_context(cadata=trust['ca_pem'])
    assert client.check_hostname and client.verify_mode == ssl.CERT_REQUIRED
    from cryptography import x509
    from cryptography.x509.oid import ExtensionOID
    leaf = x509.load_pem_x509_certificate((folder/'server.pem').read_bytes())
    assert leaf.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value.get_values_for_type(x509.DNSName) == [trust['hostname']]


def test_identity_tls_only_and_asgi_source_preserved(provisioned):
    app = FastAPI()
    trust = provisioned[1]
    lan.add_identity_route(app, trust)
    @app.get('/source')
    def source(request:Request):
        return dict(source=request.client.host, scheme=request.url.scheme)
    with TestClient(app, base_url='https://'+trust['hostname'], client=('192.168.1.27',1234)) as c:
        assert c.get(lan.IDENTITY_PATH).json() == lan.identity_response(trust)
        assert c.get('/source',headers={'X-Forwarded-For':'8.8.8.8'}).json() == dict(source='192.168.1.27',scheme='https')
    with TestClient(app) as c:
        assert c.get(lan.IDENTITY_PATH).status_code == 403


def test_public_allowlist_unchanged_for_authenticated_discovery_and_security():
    calls=[]
    with gateway_client(calls) as c:
        for path in (lan.IDENTITY_PATH,'/classroom-discovery/pair','/local-fyp/identity',
                     '/attendance/start','/verify-face','/api/v1/devices','/sessions'):
            for method in ('GET','POST'):
                assert c.request(method,path,headers={'Authorization':'Bearer synthetic-only'}).status_code == 404
    assert len(calls)==1  # loopback startup identity probe only


def test_legacy_launch_unchanged_without_profile(tmp_path):
    with patch('uvicorn.run') as run:
        app=FastAPI()
        lan.run_backend(app,host='0.0.0.0',port=8000,parent=tmp_path,mode='Full',database_identity='a'*64)
        run.assert_called_once_with(app,host='0.0.0.0',port=8000,proxy_headers=False,access_log=False)


def test_partial_provisioning_fails_closed(tmp_path):
    (tmp_path/'lan-discovery').mkdir()
    with patch('uvicorn.run') as run, pytest.raises(FileNotFoundError):
        lan.run_backend(FastAPI(),host='0.0.0.0',port=8000,parent=tmp_path,mode='Full',database_identity='a'*64)
    run.assert_not_called()


def test_launcher_rejects_unrelated_tls_process(tmp_path):
    host=FakeHost()
    host.ports.append(dict(LocalPort=8005,LocalAddress='192.168.0.8',OwningProcess=999))
    with pytest.raises(Blocked, match='DISCOVERY_PORT_IDENTITY_CONFLICT'):
        Workflow(host,tmp_path/'runtime').inventory()


def test_installer_only_exports_public_trust_never_provisions():
    script=(Path(__file__).resolve().parents[2]/'scripts'/'install-fyp-android.ps1').read_text()
    assert "lan_discovery.py') export --mode $Mode --expected-identity $ready.identity" in script
    assert 'lan_discovery.py\') provision' not in script
    assert 'FYP_LAN_TRUST_B64=' in script


def test_advertisement_is_interface_bound_and_contains_no_private_identity(provisioned, monkeypatch):
    from types import SimpleNamespace
    calls=[]
    class Zeroconf:
        def __init__(self,**kw):calls.append(('interface',kw))
        def register_service(self,info,**kw):calls.append(('register',info,kw))
        def close(self):calls.append(('close',))
    class ServiceInfo:
        def __init__(self,*args,**kw):self.args=args;self.kw=kw
    monkeypatch.setitem(sys.modules,'zeroconf',SimpleNamespace(Zeroconf=Zeroconf,
        ServiceInfo=ServiceInfo,IPVersion=SimpleNamespace(V4Only='v4')))
    publisher=lan.Advertisement('192.168.0.162',provisioned[1])
    publisher.close()
    assert calls[0]==('interface',dict(interfaces=['192.168.0.162'],ip_version='v4'))
    assert calls[1][1].args[0]==lan.SERVICE
    assert set(calls[1][1].kw['properties'])=={'v','mode','id'}
    assert calls[1][2]==dict(ttl=15)
    assert calls[-1]==('close',)


def test_lifecycle_rebind_and_cleanup_stay_in_same_process(provisioned, monkeypatch):
    folder, trust=provisioned
    servers=[]; events=[]; location=['192.168.0.162']
    class Config:
        def __init__(self,app,**kw): self.kw=kw
    class Server:
        def __init__(self,config):
            self.config=config; self.should_exit=False; self.started=False; servers.append(self)
            events.append(('created',config.kw['port']))
        async def serve(self):
            self.started=True
            events.append(('started',self.config.kw['port']))
            try:
                while not self.should_exit: await asyncio.sleep(.001)
            finally: events.append(('stopped',self.config.kw['port']))
    class Advert:
        def __init__(self,address,trust): self.address=address; events.append(('advertise',address))
        def close(self): events.append(('goodbye',self.address))
    monkeypatch.setattr('uvicorn.Config',Config)
    monkeypatch.setattr('uvicorn.Server',Server)
    monkeypatch.setattr(lan,'Advertisement',Advert)
    async def immediate(function, *args):
        return function(*args)
    monkeypatch.setattr(lan.asyncio, 'to_thread', immediate)
    async def scenario():
        task=asyncio.create_task(lan.serve(FastAPI(),host='0.0.0.0',port=8000,folder=folder,
            mode='Full',database_identity='a'*64,address=lambda:location[0],poll_seconds=.01))
        async def until(check):
            for _ in range(100):
                if task.done(): task.result()
                if check(): return
                await asyncio.sleep(.05)
            raise AssertionError('Bounded lifecycle check timed out: ' + repr(events))
        await until(lambda:('advertise',location[0]) in events)
        location[0]='10.46.58.220'
        await until(lambda:('advertise',location[0]) in events)
        servers[0].should_exit=True
        await asyncio.wait_for(task,2)
    asyncio.run(scenario())
    assert ('goodbye','192.168.0.162') in events
    assert ('goodbye','10.46.58.220') in events
    assert sum(s.config.kw['port']==8005 for s in servers)==2
    assert all(s.config.kw.get('proxy_headers') is False for s in servers)
    assert all(s.config.kw['lifespan']=='off' for s in servers[1:])


def test_relocated_installer_exports_trust_from_repository_root():
    script=(Path(__file__).resolve().parents[2]/'scripts'/'install-fyp-android.ps1').read_text()
    assert "$projectRoot = Split-Path -Parent $PSScriptRoot" in script
    assert "Join-Path $projectRoot 'backend\\venv\\Scripts\\python.exe'" in script
    assert "Join-Path $projectRoot 'backend\\lan_discovery.py'" in script
    assert "Join-Path $PSScriptRoot 'backend" not in script
    assert 'FYP_LAN_TRUST_B64' in script
    assert '--expected-identity $ready.identity' in script
