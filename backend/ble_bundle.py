"""Package the existing BleProbe bytes, without compiling or running Bluetooth.

Only the declared, exact Windows SDK runtime-pack dependencies are supported.
No download, latest-version fallback, external-source edit or BLE substitution.
"""
import hashlib
import json
from pathlib import Path
import re


class BundleError(RuntimeError):
    pass


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(source, destination, cache, identity, *, running=False):
    source, destination, cache = Path(source), Path(destination), Path(cache)
    core = [source, source.with_suffix('.dll'), source.with_suffix('.deps.json'),
            source.with_suffix('.runtimeconfig.json')]
    if not all(path.is_file() for path in core):
        raise BundleError('BLE_CORE_OR_DEPENDENCY_MANIFEST_MISSING')
    manifest = json.loads(source.with_suffix('.deps.json').read_text())
    target = manifest['targets'][manifest['runtimeTarget']['name']]
    files = {path.name:path for path in core}
    required = {}
    for library, data in target.items():
        for name, versions in data.get('runtime', {}).items():
            if name == 'BleProbe.dll':
                continue
            if name not in ('Microsoft.Windows.SDK.NET.dll', 'WinRT.Runtime.dll'):
                raise BundleError('BLE_UNSUPPORTED_RUNTIME_DEPENDENCY')
            pack, version = library.rsplit('/', 1)
            if pack != 'runtimepack.Microsoft.Windows.SDK.NET.Ref' or not re.fullmatch(r'\d+(\.\d+)+', version):
                raise BundleError('BLE_UNSUPPORTED_RUNTIME_PACK')
            local = source.parent / name
            cached = cache / 'microsoft.windows.sdk.net.ref' / version / 'lib/net8.0' / name
            path = local if local.is_file() else cached
            if not path.is_file():
                raise BundleError('BLE_EXACT_RUNTIME_DEPENDENCY_MISSING_' + name)
            actual = identity(path)  # Assembly metadata only; never invoke its entry point.
            if (actual.get('name') != Path(name).stem
                    or actual.get('version') != versions.get('assemblyVersion')
                    or actual.get('fileVersion') != versions.get('fileVersion')):
                raise BundleError('BLE_RUNTIME_DEPENDENCY_VERSION_MISMATCH_' + name)
            files[name] = path
            required[name] = actual
    if set(required) != {'Microsoft.Windows.SDK.NET.dll', 'WinRT.Runtime.dll'}:
        raise BundleError('BLE_WINDOWS_RUNTIME_DEPENDENCIES_NOT_DECLARED')
    hashes = {name:digest(path) for name,path in files.items()}
    changes = [name for name in files if not (destination / name).is_file()
               or digest(destination / name) != hashes[name]]
    if changes and running:
        raise BundleError('BLE_BUNDLE_UPDATE_REQUIRES_APPROVED_STOP')
    destination.mkdir(parents=True, exist_ok=True)
    for name in changes:
        temporary = destination / (name + '.tmp')
        temporary.write_bytes(files[name].read_bytes())
        temporary.replace(destination / name)
        if digest(destination / name) != hashes[name]:
            raise BundleError('BLE_BUNDLE_COPY_HASH_MISMATCH')
    receipt = dict(source=str(source), implementation='unchanged-existing-GATT-BleProbe',
                   files_sha256=hashes, runtime_assemblies=required)
    path = destination / 'bundle-manifest.json'
    text = json.dumps(receipt, indent=2)
    if not path.exists() or path.read_text() != text:
        temporary = destination / 'bundle-manifest.tmp'
        temporary.write_text(text)
        temporary.replace(path)
    return destination / source.name
