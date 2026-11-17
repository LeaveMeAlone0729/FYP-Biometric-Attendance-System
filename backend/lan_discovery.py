"""Opt-in direct TLS classroom listener. No DB connection or public gateway change.

Provisioning is an explicit offline operator action, never called by start/install.
The existing backend process owns both listeners and the interface-bound advertiser.
"""
import argparse
import asyncio
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import uuid

PORT = 8005
SERVICE = '_fyp-classroom._tcp.local.'
IDENTITY_PATH = '/classroom-discovery/identity'


def require(value, message):
    if not value:
        raise ValueError(message)


def private(mode):
    require(mode in ('Full', 'Local'), 'DISCOVERY_MODE_INVALID')
    if mode == 'Full':
        from original_fyp import PRIVATE
        return PRIVATE
    from local_fyp import private as local_private
    return local_private()


def private_ip(value):
    ip = ipaddress.IPv4Address(value)
    require(any(ip in ipaddress.ip_network(n) for n in
                ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')),
            'DISCOVERY_PRIVATE_WIFI_REQUIRED')
    return str(ip)


def restrict_folder(folder):
    # Only the NEW discovery folder is changed; no inherited production ACLs.
    if os.name == 'nt':
        user = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'],
            text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        sid = re.search(r'S-1-5-[0-9-]+', user).group()
        subprocess.run(['icacls', str(folder), '/inheritance:r', '/grant:r',
            f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'], check=True,
            capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        folder.chmod(0o700)


def provision(folder, mode, database_identity, *, protect=restrict_folder):
    """New CA and leaf; CA signing key is discarded, never reused as server key."""
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    require(mode in ('Full', 'Local') and re.fullmatch('[0-9a-f]{64}', database_identity),
            'DISCOVERY_IDENTITY_INVALID')
    folder.mkdir(mode=0o700, parents=False, exist_ok=False)
    protect(folder)
    identifier = uuid.uuid4().hex
    hostname = 'fyp-' + identifier + '.local'
    now = datetime.now(timezone.utc)
    ca_key, key = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'FYP private ' + mode + ' CA ' + identifier)])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
        .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=1095))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
        .sign(ca_key, hashes.SHA256()))
    cert = (x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)]))
        .issuer_name(ca_name).public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=730))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), critical=True)
        .sign(ca_key, hashes.SHA256()))
    pem = ca.public_bytes(serialization.Encoding.PEM).decode()
    trust = dict(version=1, mode=mode, server_id=identifier, hostname=hostname,
        port=PORT, database_identity=database_identity, ca_pem=pem)
    (folder / 'server.key').write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (folder / 'server.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (folder / 'public-trust.json').write_text(json.dumps(trust), encoding='utf-8')
    return trust


def load_trust(folder, mode, database_identity):
    from cryptography import x509
    trust = json.loads((folder / 'public-trust.json').read_text(encoding='utf-8'))
    require(set(trust) == {'version','mode','server_id','hostname','port','database_identity','ca_pem'},
            'DISCOVERY_TRUST_FIELDS_INVALID')
    require(trust['version'] == 1 and trust['mode'] == mode
        and trust['database_identity'] == database_identity and trust['port'] == PORT
        and re.fullmatch('[0-9a-f]{32}', trust['server_id'])
        and trust['hostname'] == 'fyp-' + trust['server_id'] + '.local', 'DISCOVERY_TRUST_BINDING_MISMATCH')
    ca = x509.load_pem_x509_certificate(trust['ca_pem'].encode())
    leaf = x509.load_pem_x509_certificate((folder / 'server.pem').read_bytes())
    leaf.verify_directly_issued_by(ca)
    require(leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        .get_values_for_type(x509.DNSName) == [trust['hostname']], 'DISCOVERY_CERTIFICATE_NAME_MISMATCH')
    now = datetime.now(timezone.utc)
    require(ca.not_valid_before_utc <= now < ca.not_valid_after_utc
        and leaf.not_valid_before_utc <= now < leaf.not_valid_after_utc,
        'DISCOVERY_CERTIFICATE_EXPIRED_OR_NOT_YET_VALID')
    import ssl
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(folder / 'server.pem', folder / 'server.key')
    return trust


def identity_response(trust):
    return {k: trust[k] for k in ('version','mode','server_id','database_identity')}


def probe_tls(address, trust):
    """Bounded operator readiness check: real TLS, no bearer or DB query."""
    import ssl
    import http.client
    context = ssl.create_default_context(cadata=trust['ca_pem'])
    with socket.create_connection((private_ip(address), PORT), timeout=3) as raw:
        with context.wrap_socket(raw, server_hostname=trust['hostname']) as tls:
            tls.sendall(('GET ' + IDENTITY_PATH + ' HTTP/1.1\r\nHost: ' + trust['hostname'] +
                         ':8005\r\nConnection: close\r\n\r\n').encode())
            response = http.client.HTTPResponse(tls)
            response.begin()
            data = response.read(2049)
            require(response.status == 200 and len(data) <= 2048 and
                json.loads(data) == identity_response(trust), 'DISCOVERY_TLS_IDENTITY_MISMATCH')
    return True


def add_identity_route(app, trust):
    from fastapi import Request, HTTPException
    @app.get(IDENTITY_PATH, include_in_schema=False)
    def discovery_identity(request: Request):
        if request.url.scheme != 'https':
            raise HTTPException(403, 'TLS_REQUIRED')
        from fastapi.responses import JSONResponse
        return JSONResponse(identity_response(trust), headers={'cache-control': 'no-store'})


class Advertisement:
    def __init__(self, address, trust):
        from zeroconf import IPVersion, ServiceInfo, Zeroconf
        address = private_ip(address)
        self.zc = Zeroconf(interfaces=[address], ip_version=IPVersion.V4Only)
        self.info = ServiceInfo(SERVICE, 'FYP-' + trust['server_id'] + '.' + SERVICE,
            addresses=[socket.inet_aton(address)], port=PORT,
            properties={'v':'1', 'mode':trust['mode'], 'id':trust['server_id']},
            server=trust['hostname'] + '.')
        try:
            self.zc.register_service(self.info, ttl=15)
        except BaseException:
            self.zc.close()
            raise

    def close(self):
        self.zc.close()  # unregisters, sends goodbye and closes sockets


async def serve(app, *, host, port, folder, mode, database_identity, address=None, poll_seconds=3):
    import uvicorn
    class Secondary(uvicorn.Server):
        def capture_signals(self):
            return nullcontext()  # only the primary owns Ctrl+C/termination
    trust = load_trust(folder, mode, database_identity)
    add_identity_route(app, trust)
    primary = uvicorn.Server(uvicorn.Config(app, host=host, port=port,
        proxy_headers=False, access_log=False))
    secondary = task = advertiser = None

    async def stop_secondary():
        nonlocal secondary, task, advertiser
        if advertiser:
            await asyncio.to_thread(advertiser.close)
            advertiser = None
        if secondary:
            secondary.should_exit = True
            await asyncio.wait_for(task, 8)
            secondary = task = None

    async def monitor():
        nonlocal secondary, task, advertiser
        current = None
        while not primary.should_exit:
            if not primary.started:
                await asyncio.sleep(.1)
                continue
            try:
                if address:
                    candidate = private_ip(await asyncio.to_thread(address))
                else:
                    from fyp_operator import Host
                    candidate = private_ip(await asyncio.to_thread(Host().lan))
            except Exception:
                candidate = None
            if candidate != current or (task and task.done()):
                await stop_secondary()
                current = candidate
                if candidate:
                    secondary = Secondary(uvicorn.Config(app, host=candidate, port=PORT,
                        ssl_keyfile=str(folder / 'server.key'), ssl_certfile=str(folder / 'server.pem'),
                        lifespan='off', proxy_headers=False, access_log=False,
                        timeout_graceful_shutdown=5))
                    task = asyncio.create_task(secondary.serve())
                    for _ in range(50):
                        if task.done() or secondary.started:
                            break
                        await asyncio.sleep(.1)
                    require(secondary.started and not task.done(), 'DISCOVERY_TLS_LISTENER_FAILED')
                    # Failure to advertise must not disable authenticated manual-IP recovery.
                    try:
                        publication = asyncio.create_task(asyncio.to_thread(Advertisement, candidate, trust))
                        try:
                            advertiser = await asyncio.shield(publication)
                        except asyncio.CancelledError:
                            # A thread cannot be cancelled: retain the returned owner
                            # so outer cleanup unregisters even during Ctrl+C/startup.
                            advertiser = await publication
                            raise
                    except Exception:
                        print('DISCOVERY_MULTICAST_UNAVAILABLE_USE_PAIRED_MANUAL_ADDRESS', flush=True)
            await asyncio.sleep(poll_seconds)

    primary_task, monitor_task = asyncio.create_task(primary.serve()), asyncio.create_task(monitor())
    try:
        done, _ = await asyncio.wait([primary_task, monitor_task], return_when=asyncio.FIRST_COMPLETED)
        for finished in done:
            finished.result()
    finally:
        primary.should_exit = True
        monitor_task.cancel()
        await asyncio.gather(monitor_task, return_exceptions=True)
        await stop_secondary()
        await primary_task


def run_backend(app, *, host, port, parent, mode, database_identity):
    folder = parent / 'lan-discovery'
    if not folder.exists():
        import uvicorn
        uvicorn.run(app, host=host, port=port, proxy_headers=False, access_log=False)
    else:
        require(host == '0.0.0.0', 'DISCOVERY_REQUIRES_SUPPORTED_LAN_START')
        asyncio.run(serve(app, host=host, port=port, folder=folder, mode=mode,
                          database_identity=database_identity))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('provision','export'))
    p.add_argument('--mode', required=True, choices=('Full','Local'))
    p.add_argument('--expected-identity')
    a = p.parse_args()
    parent = private(a.mode)
    pin = json.loads((parent / 'identity.json').read_text(encoding='utf-8'))
    if a.mode == 'Full':
        from original_fyp import public_identity
        expected = public_identity(pin)['identity']
    else:
        from local_fyp import public_identity
        expected = public_identity(pin)['identity']
    folder = parent / 'lan-discovery'
    if a.action == 'provision':
        require(input('Create a NEW private LAN identity for ' + a.mode + '; type PAIR: ') == 'PAIR',
                'DISCOVERY_PROVISION_NOT_CONFIRMED')
        provision(folder, a.mode, expected)
        print('PUBLIC_TRUST_CREATED_IN_PRIVATE_FOLDER_REVIEW_BEFORE_INSTALL')
    elif folder.exists():
        require(a.expected_identity == expected, 'DISCOVERY_INSTALLER_IDENTITY_MISMATCH')
        print(json.dumps(load_trust(folder, a.mode, expected), separators=(',',':')))
    # Absent profile is explicit legacy mode, not a partially provisioned fallback.


if __name__ == '__main__':
    main()
