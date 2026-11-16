"""Allowlisted internet ingress for the ORIGINAL backend. No database connection.

Run locally only; cloudflared must target this listener, never port 8000/8003.
Classroom, biometric, device-management and internal routes are intentionally absent.
"""
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import httpx
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

ALLOWED = {
    '/config': {'GET'}, '/login': {'POST'}, '/logout': {'POST'},
    '/me': {'GET'}, '/classes': {'GET'}, '/attendance/history': {'GET'},
    '/attendance/summary': {'GET'},
}
ORIGIN = 'http://127.0.0.1:8000'
LOGIN_LIMIT = 60
LOGIN_WINDOW_SECONDS = 60


def create_gateway(hostname, *, transport=None, clock=time.monotonic):
    parsed = urlsplit('https://' + hostname)
    if (not hostname or parsed.hostname != hostname or '.' not in hostname
            or parsed.port is not None or parsed.path or parsed.query or parsed.fragment
            or parsed.username or hostname != hostname.lower()
            or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-.' for c in hostname)):
        raise ValueError('FYP_PUBLIC_HOST must be the actual hostname, without scheme or port.')

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(base_url=ORIGIN, transport=transport,
                timeout=httpx.Timeout(10, connect=3), trust_env=False,
                follow_redirects=False) as client:
            # Existing original identity contract, not a second application/database.
            identity = await client.get('/local-fyp/identity')
            value = identity.json()
            if (identity.status_code != 200 or value.get('environment') != 'original'
                    or value.get('db_port') != 3306
                    or value.get('database') != 'attendance_proposal_xampp'):
                raise RuntimeError('ORIGINAL_BACKEND_IDENTITY_REQUIRED')
            app.state.client = client
            yield

    app = Starlette(lifespan=lifespan)
    login_requests = deque()

    async def gateway(request, call_next):
        # The local listener is private and trusted only as an ingress transport.
        # No forwarding header or proxy IP is converted to classroom presence.
        if request.scope.get('client', ('',))[0] not in ('127.0.0.1', '::1'):
            return JSONResponse({'code': 'PUBLIC_ORIGIN_LOCAL_ONLY'}, 403)
        if request.headers.get('host') != hostname:
            return JSONResponse({'code': 'PUBLIC_HOST_REJECTED'}, 403)
        path = request.scope.get('raw_path', b'').decode('ascii', 'replace')
        if path not in ALLOWED or request.method not in ALLOWED[path] or request.url.query:
            return JSONResponse({'code': 'PUBLIC_ROUTE_NOT_AVAILABLE'}, 404)
        if path == '/login':
            # Single gateway process/event loop: no await between pruning/check/append.
            # Aggregate limit deliberately does not trust a proxy/client IP header.
            now = clock()
            while login_requests and login_requests[0] <= now - LOGIN_WINDOW_SECONDS:
                login_requests.popleft()
            if len(login_requests) >= LOGIN_LIMIT:
                return JSONResponse({'code': 'PUBLIC_LOGIN_RATE_LIMITED',
                    'message': 'Too many sign-in requests. Try again in one minute.'},
                    429, headers={'retry-after': str(LOGIN_WINDOW_SECONDS)})
            login_requests.append(now)
        body = bytearray()
        async for part in request.stream():
            body.extend(part)
            if len(body) > 8192:
                return JSONResponse({'code': 'PUBLIC_BODY_TOO_LARGE'}, 413)
        headers = {'content-type': 'application/json'}
        authorization = request.headers.get('authorization')
        if authorization:
            headers['authorization'] = authorization
        try:
            response = await app.state.client.request(request.method, path,
                content=bytes(body), headers=headers)
        except httpx.HTTPError:
            return JSONResponse({'code': 'PUBLIC_ORIGIN_UNAVAILABLE',
                'message': 'Unable to reach the application server.'}, 503)
        # Do not leak origin cookies, redirects or technical forwarding headers.
        return Response(response.content, response.status_code,
            headers={'cache-control': 'no-store', 'x-content-type-options': 'nosniff'},
            media_type='application/json')
    app.add_middleware(BaseHTTPMiddleware, dispatch=gateway)
    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(create_gateway(os.environ.get('FYP_PUBLIC_HOST', '')),
                host='127.0.0.1', port=8004, proxy_headers=False, access_log=False)
