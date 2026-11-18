"""Packaging and monitoring tests; no Bluetooth API or live service is invoked."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ble_bundle import prepare, BundleError, digest
from fyp_operator import BeaconExited, Host
from test_fyp_operator import workflow


@pytest.fixture
def bundle(tmp_path):
    source=tmp_path / 'original/BleProbe.exe'
    source.parent.mkdir()
    for name in ('BleProbe.exe','BleProbe.dll','BleProbe.runtimeconfig.json'):
        (source.parent/name).write_bytes(('unchanged-'+name).encode())
    versions={'assemblyVersion':'1.2.3.4','fileVersion':'1.2.3.5'}
    manifest={'runtimeTarget':{'name':'target'},'targets':{'target':{
        'BleProbe/1.0.0':{'runtime':{'BleProbe.dll':{}}},
        'runtimepack.Microsoft.Windows.SDK.NET.Ref/10.0.26100.57':{'runtime':{
            'Microsoft.Windows.SDK.NET.dll':versions,'WinRT.Runtime.dll':versions}}}}}
    source.with_suffix('.deps.json').write_text(json.dumps(manifest))
    cache=tmp_path/'cache'
    lib=cache/'microsoft.windows.sdk.net.ref/10.0.26100.57/lib/net8.0'
    lib.mkdir(parents=True)
    for name in ('Microsoft.Windows.SDK.NET.dll','WinRT.Runtime.dll'):
        (lib/name).write_text('matching-runtime-'+name)
    identity=lambda path:dict(name=path.stem,version='1.2.3.4',fileVersion='1.2.3.5')
    return source,tmp_path/'prepared',cache,identity


def test_missing_app_local_dependencies_recovered_without_changing_original(bundle):
    source,destination,cache,identity=bundle
    before={p.name:digest(p) for p in source.parent.iterdir()}
    result=prepare(*bundle)
    assert result == destination/'BleProbe.exe'
    assert {p.name:digest(p) for p in source.parent.iterdir()} == before
    assert digest(result) == digest(source)
    assert digest(result.with_suffix('.dll')) == digest(source.with_suffix('.dll'))
    assert (destination/'Microsoft.Windows.SDK.NET.dll').is_file()
    assert (destination/'WinRT.Runtime.dll').is_file()
    prepare(*bundle,running=True)  # Idempotent; no rewrite of active identical files.


def test_exact_cache_version_missing_does_not_choose_latest(bundle):
    source,destination,cache,identity=bundle
    (cache/'microsoft.windows.sdk.net.ref/10.0.26100.57/lib/net8.0/WinRT.Runtime.dll').unlink()
    with pytest.raises(BundleError,match='EXACT_RUNTIME_DEPENDENCY_MISSING'):
        prepare(*bundle)
    assert not destination.exists()


def test_mismatched_assembly_version_rejected(bundle):
    source,destination,cache,_=bundle
    with pytest.raises(BundleError,match='VERSION_MISMATCH'):
        prepare(source,destination,cache,lambda path:dict(name=path.stem,version='wrong',fileVersion='wrong'))


def test_active_bundle_never_overwritten(bundle):
    source,destination,cache,identity=bundle
    prepare(*bundle)
    source.with_suffix('.dll').write_bytes(b'updated-original')
    with pytest.raises(BundleError,match='REQUIRES_APPROVED_STOP'):
        prepare(*bundle,running=True)
    assert (destination/'BleProbe.dll').read_bytes() != source.with_suffix('.dll').read_bytes()


def test_unexpected_manifest_runtime_library_rejected(bundle):
    source,destination,cache,identity=bundle
    value=json.loads(source.with_suffix('.deps.json').read_text())
    value['targets']['target']['other/1.0']={'runtime':{'../unexpected.dll':{}}}
    source.with_suffix('.deps.json').write_text(json.dumps(value))
    with pytest.raises(BundleError,match='UNSUPPORTED_RUNTIME_DEPENDENCY'):
        prepare(*bundle)


def test_beacon_launch_uses_its_bundle_directory(tmp_path,monkeypatch):
    import fyp_operator
    host=Host()
    args=[str(tmp_path/'BleProbe.exe'),'--continuous']
    observed={}
    def launch(*_args,**kwargs):
        observed.update(kwargs)
        return SimpleNamespace(pid=123)
    monkeypatch.setattr(fyp_operator.subprocess,'Popen',launch)
    monkeypatch.setattr(host,'process',lambda _:dict(ProcessId=123))
    host.launch(args,'beacon',tmp_path)
    assert observed['cwd'] == tmp_path


def test_failed_publisher_exits_immediately_with_code_and_log(tmp_path):
    flow=workflow(tmp_path)
    original=flow.host.launch
    def failed(args,role,logs):
        child,row=original(args,role,logs)
        if role=='beacon':
            child.poll=lambda:23
        return child,row
    flow.host.launch=failed
    with pytest.raises(BeaconExited,match=r'exit_code=23; log: .*beacon.err.log'):
        flow.start()


def test_healthy_existing_probe_reused_without_repackaging(tmp_path):
    first=workflow(tmp_path/'first')
    first.start()
    second=workflow(tmp_path/'second',first.host,answer='DETECTED')
    second.host.beacon=lambda:pytest.fail('Existing healthy process must not be rebuilt/replaced')
    second.start()
    assert not second.state


def test_retries_in_same_second_have_distinct_publisher_logs(tmp_path,monkeypatch):
    import fyp_operator
    monkeypatch.setattr(fyp_operator.time,'strftime',lambda _:'same-second')
    first=workflow(tmp_path)
    second=workflow(tmp_path)
    assert first.logs != second.logs
