"""Offline public ingress tests. No real database or Cloudflare access."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
import pytest
from starlette.testclient import TestClient
from public_gateway import create_gateway, LOGIN_LIMIT

HOST = 'fyp.test.example'


def client(calls, *, bad_identity=False):
    def origin(request):
        calls.append(request)
        if request.url.path == '/local-fyp/identity':
            return httpx.Response(200, json=dict(environment='wrong' if bad_identity else 'original',
                db_port=3306, database='attendance_proposal_xampp'))
        return httpx.Response(200, json={'success': True})
    return TestClient(create_gateway(HOST, transport=httpx.MockTransport(origin)),
                      base_url='https://' + HOST, client=('127.0.0.1', 40000))


def test_general_api_and_forwarding_headers_stripped():
    calls = []
    with client(calls) as c:
        for method, path in [('POST','/login'), ('GET','/me'), ('GET','/classes'),
                            ('GET','/attendance/history'), ('POST','/logout')]:
            r = c.request(method, path, json={}, headers={'Authorization':'Bearer synthetic-test',
                'CF-Connecting-IP':'192.168.0.22', 'X-Forwarded-For':'192.168.0.22'})
            assert r.status_code == 200
            assert r.headers['cache-control'] == 'no-store'
            assert 'cf-connecting-ip' not in calls[-1].headers
            assert 'x-forwarded-for' not in calls[-1].headers
            assert calls[-1].headers['authorization'] == 'Bearer synthetic-test'


@pytest.mark.parametrize('path', ['/attendance/start','/verify-face','/liveness/frame',
    '/api/v1/networks/verifications','/api/v1/devices','/register','/register-face',
    '/local-fyp/identity','/local-fyp/demo-slot2','/docs','/openapi.json','/ble',
    '/api/v1/network-ble-tests/start','/api/v1/classroom-wifi/challenges'])
def test_sensitive_routes_never_reach_origin(path):
    calls=[]
    with client(calls) as c:
        count=len(calls)
        assert c.post(path, json={}).status_code == 404
        assert c.get(path).status_code == 404
        assert len(calls) == count


def test_host_method_query_body_and_identity():
    with client([]) as c:
        assert c.get('/me',headers={'host':'attacker.example'}).status_code == 403
        assert c.delete('/me').status_code == 404
        assert c.get('/me?path=/attendance/start').status_code == 404
        assert c.post('/login',content=b'x'*8193).status_code == 413
    with pytest.raises(RuntimeError):
        with client([], bad_identity=True):
            pass
    for name in ['', 'https://example.com', 'example.com/path', 'example.com:443']:
        with pytest.raises(ValueError):
            create_gateway(name)


def test_authentication_failures_throttle_and_origin_timeout_remain_fail_closed():
    for status in (401, 403, 429, 503):
        def origin(request):
            if request.url.path == '/local-fyp/identity':
                return httpx.Response(200, json=dict(environment='original', db_port=3306,
                                                     database='attendance_proposal_xampp'))
            if status == 503:
                raise httpx.ConnectTimeout('synthetic unreachable origin')
            return httpx.Response(status, json={'message':'Denied by original authentication'})
        app=create_gateway(HOST, transport=httpx.MockTransport(origin))
        with TestClient(app, base_url='https://' + HOST, client=('127.0.0.1',40000)) as c:
            assert c.post('/login', json={}).status_code == status


def test_aggregate_login_limit_ignores_forged_client_headers_and_expires():
    now = [100.0]
    calls = []
    def origin(request):
        calls.append(request.url.path)
        if request.url.path == '/local-fyp/identity':
            return httpx.Response(200, json=dict(environment='original', db_port=3306,
                                                database='attendance_proposal_xampp'))
        return httpx.Response(401, json={'message':'Synthetic invalid account'})
    app = create_gateway(HOST, transport=httpx.MockTransport(origin), clock=lambda: now[0])
    with TestClient(app, base_url='https://' + HOST, client=('127.0.0.1',40000)) as c:
        for index in range(LOGIN_LIMIT):
            assert c.post('/login', json={'student_id':f'SYNTHETIC{index}'},
                headers={'CF-Connecting-IP':f'192.0.2.{index+1}'}).status_code == 401
        assert c.post('/login', json={}).status_code == 429
        assert calls.count('/login') == LOGIN_LIMIT
        assert c.get('/config').status_code == 401  # Original mock auth status, not rate-limited.
        now[0] += 60
        assert c.post('/login', json={}).status_code == 401


@pytest.mark.parametrize('path', ['/admin', '/sessions', '/wifi', '/networks',
    '/verification/test', '/api/v1/attendance/preflight-challenges',
    '/api/v1/classroom-ble/challenges', '/api/v1/device-approvals',
    '/api/v1/devices/pending-registrations', '/redoc', '/login/',
    '/%6cogin', '/login%2f..%2fattendance/start'])
def test_additional_sensitive_and_encoded_paths_are_not_forwarded(path):
    calls=[]
    with client(calls) as c:
        count=len(calls)
        assert c.post(path, json={}).status_code == 404
        assert len(calls) == count


def test_nonloopback_requests_rejected_even_with_local_forwarding_claim():
    calls=[]
    def origin(request):
        calls.append(request.url.path)
        return httpx.Response(200, json=dict(environment='original', db_port=3306,
                                            database='attendance_proposal_xampp'))
    app=create_gateway(HOST, transport=httpx.MockTransport(origin))
    with TestClient(app, base_url='https://' + HOST, client=('192.0.2.45',40000)) as c:
        assert c.get('/config', headers={'X-Forwarded-For':'127.0.0.1'}).status_code == 403
        assert calls == ['/local-fyp/identity']


def test_valid_isolated_backend_session_does_not_unlock_sensitive_routes():
    # Real application login/token validation, disposable in-memory SQLite only.
    # The synthetic origin bridge does not connect to original MariaDB.
    import test_device_registration as registration
    registration.DeviceRegistrationTests.setUpClass()
    fixture = registration.DeviceRegistrationTests()
    fixture.setUp()
    calls=[]
    try:
        assert fixture.client.get('/me', headers=fixture.headers).status_code == 200
        def origin(request):
            calls.append(request.url.path)
            if request.url.path == '/local-fyp/identity':
                return httpx.Response(200, json=dict(environment='original', db_port=3306,
                                                    database='attendance_proposal_xampp'))
            response=fixture.client.request(request.method, request.url.path,
                content=request.content, headers=dict(request.headers))
            return httpx.Response(response.status_code, content=response.content)
        app=create_gateway(HOST, transport=httpx.MockTransport(origin))
        with TestClient(app, base_url='https://' + HOST, client=('127.0.0.1',40000)) as c:
            assert c.get('/me', headers=fixture.headers).status_code == 200
            count=len(calls)
            for path in ('/attendance/start', '/verify-face', '/liveness/frame',
                '/api/v1/attendance/preflight-challenges', '/api/v1/devices',
                '/api/v1/classroom-wifi/challenges', '/api/v1/classroom-ble/challenges',
                '/api/v1/network-ble-tests/start', '/local-fyp/identity', '/ble', '/sessions'):
                assert c.post(path, json={}, headers=fixture.headers).status_code == 404
                assert c.get(path, headers=fixture.headers).status_code == 404
            assert len(calls) == count
            assert fixture.count(registration.Attendance) == 0
    finally:
        fixture.tearDown()
