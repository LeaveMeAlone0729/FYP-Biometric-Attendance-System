"""Local-only operator HTML. No student, biometric, approval or attendance writer routes."""
import hmac
import ipaddress
import secrets
import threading
import time
from datetime import datetime
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from security import verify_password
from manual_android_test import ManualTestGuardError

COOKIE = 'fyp_testing_admin'
PAGES = {'sessions': 'Attendance Sessions', 'networks': 'Network Policies',
         'wifi': 'Classroom Wi-Fi', 'ble': 'Experimental BLE'}
BRAND = 'FYP Attendance Management System'
PAGE_INTROS = {
    'sessions': 'Create sessions, share attendance PINs and review submissions.',
    'networks': 'Manage the IP ranges allowed for attendance.',
    'wifi': 'Manage the access points approved for each classroom.',
    'ble': 'Configure classroom beacons for testing.',
}


def text(value):
    return escape(str(value), quote=True)


def field(name, label, kind='text', value='', required=True):
    return (f'<label>{text(label)} <input name="{text(name)}" type="{kind}" '
            f'value="{text(value)}" maxlength="128" {"required" if required else ""}></label>')


def choice(name, label, options):
    return f'<label>{text(label)} <select name="{name}">' + ''.join(
        f'<option value="{text(value)}">{text(label)}</option>' for value, label in options) + '</select></label>'


def form(path, csrf, body, button, *, variant='secondary', grid=False, confirmation=None, **hidden):
    values = {'csrf': csrf, **hidden}
    dialog = (f' data-confirm-title="{text(confirmation[0])}" data-confirm-detail="{text(confirmation[1])}"'
              if confirmation else '')
    layout = ' class="form-grid"' if grid else ''
    return f'<form method="post" action="{path}"{layout}{dialog}>' + ''.join(
        f'<input type="hidden" name="{text(k)}" value="{text(v)}">' for k, v in values.items()
    ) + body + f'<button class="button {variant}" type="submit">{text(button)}</button></form>'


def card(title, description, body):
    return (f'<section class="card"><div class="card-heading"><h2>{text(title)}</h2>'
            f'<p>{text(description)}</p></div>{body}</section>')


def cell(key, value):
    if key == 'expires_at':
        expiry = datetime.fromisoformat(value)
        return (f'<time datetime="{text(value)}">{expiry:%d %b %Y}'
                f'<span>{expiry:%H:%M %Z}</span></time>')
    if key in ('window_state', 'policy_state', 'status'):
        tone = ('positive' if value in ('OPEN', 'Enabled', 'active') else
                'warning' if value in ('EXPIRED', 'SCHEDULED', 'OUTSIDE_SCHEDULE') else 'neutral')
        return f'<span class="badge {tone}">{text(value)}</span>'
    return text(value)


def table(rows, columns, controls=None):
    head = ''.join(f'<th scope="col">{text(label)}</th>' for _, label in columns)
    if controls:
        head += '<th scope="col">Actions</th>'
    body = ''.join('<tr>' + ''.join(f'<td class="col-{k}">{cell(k, row.get(k, ""))}</td>' for k, _ in columns)
                   + (f'<td><div class="row-actions">{controls(row) or "—"}</div></td>' if controls else '')
                   + '</tr>' for row in rows)
    if not body:
        body = f'<tr><td class="empty" colspan="{len(columns) + bool(controls)}">No records yet.</td></tr>'
    return '<div class="scroll"><table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>'


def document(title, body, csrf=None, *, description=''):
    signout = '' if csrf is None else form('/logout', csrf, '', 'Sign out', variant='header-button')
    active = ' aria-current="page"'
    nav = '' if csrf is None else '<nav aria-label="Administration">' + ''.join(
        f'<a href="/{key}"{active if title == label else ""}>{label}</a>'
        for key, label in PAGES.items()) + '</nav>'
    intro = f'<p>{text(description)}</p>' if description else ''
    return HTMLResponse('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{text(title)} · {BRAND}</title><link rel="stylesheet" href="/admin-testing.css">'
        '<script src="/admin-testing.js" defer></script></head><body>'
        f'<header class="site-header"><div class="shell"><div class="brand-bar">'
        f'<span class="brand-mark" aria-hidden="true">FYP</span><strong>{BRAND}</strong>{signout}'
        f'</div>{nav}</div></header><main class="shell"><div class="page-heading">'
        f'<h1>{text(title)}</h1>{intro}</div>{body}</main></body></html>')


class AdminSessions:
    """Opaque memory-only sessions; a server restart signs every admin out."""
    def __init__(self, clock):
        self.clock, self.rows, self.failures = clock, {}, []
        self.lock = threading.RLock()

    def lookup(self, token):
        now = self.clock()
        with self.lock:
            self.rows = {k: v for k, v in self.rows.items() if v['expires'] > now}
            return self.rows.get(token)

    def mint(self, authenticated=False):
        with self.lock:
            self.lookup(None)
            if len(self.rows) >= 256:
                self.rows.pop(next(iter(self.rows)))
            token = secrets.token_urlsafe(32)
            self.rows[token] = dict(admin=authenticated, csrf=secrets.token_urlsafe(32),
                                    expires=self.clock() + (1800 if authenticated else 600))
            return token, self.rows[token]


def create_panel(engine, *, username, password_hash, ready, timezone='Asia/Kuala_Lumpur',
                 port=8003, clock=time.monotonic, now=None, database_port=3322,
                 simulation_only=True):
    """Engine/clock injection is for offline tests; the CLI always uses pinned operator_engine."""
    if port in (8000, 8002) or not 1024 <= port <= 65535:
        raise ValueError('Use a separate local management port, default 8003.')
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    sessions = AdminSessions(clock)
    current_time = now or (lambda: datetime.now(ZoneInfo(timezone)).replace(tzinfo=None))
    hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}

    @app.middleware('http')
    async def local_only(request, call_next):
        try:
            local = ipaddress.ip_address(request.client.host).is_loopback
        except (ValueError, AttributeError):
            local = False
        if not local or request.headers.get('host', '').lower() not in hosts:
            return HTMLResponse('Localhost access only.', status_code=403)
        if request.method == 'POST':
            if request.headers.get('origin') != 'http://' + request.headers.get('host', ''):
                return HTMLResponse('Origin rejected.', status_code=403)
            if request.headers.get('content-type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                return HTMLResponse('Use a standard HTML form.', status_code=415)
            if len(await request.body()) > 8192:
                return HTMLResponse('Form too large.', status_code=413)
        response = await call_next(request)
        response.headers.update({'Cache-Control': 'no-store', 'Pragma': 'no-cache',
            # no-referrer makes native HTML form POSTs send Origin: null in
            # browsers. Keep our exact same-origin POST check and retain origin
            # on local submissions, without sending referrers cross-origin.
            'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin',
            'Content-Security-Policy': "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"})
        return response

    def identity(request):
        row = sessions.lookup(request.cookies.get(COOKIE))
        return row if row and row['admin'] else None

    def cookie(response, token):
        response.set_cookie(COOKIE, token, httponly=True, samesite='strict', max_age=1800, path='/')
        return response

    async def checked_form(request, row):
        data = await request.form(max_fields=30)
        if any(len(data.getlist(k)) != 1 for k in data) or not hmac.compare_digest(str(data.get('csrf', '')).encode(), row['csrf'].encode()):
            raise ValueError('CSRF_INVALID: reload this page before submitting.')
        return dict(data)

    @app.get('/login')
    def login_page(request: Request):
        if identity(request):
            return RedirectResponse('/sessions', status_code=303)
        token, row = sessions.mint()
        return cookie(document('Admin login', '<section class="card login-card">' +
            form('/login', row['csrf'], field('username', 'Admin username') + field('password', 'Password', 'password'),
                 'Sign in', variant='primary', grid=True) + '</section>',
            description='Sign in with your administrator account.'), token)

    @app.post('/login')
    async def login(request: Request):
        row = sessions.lookup(request.cookies.get(COOKIE))
        if row is None:
            return HTMLResponse('Login form expired. Reload /login.', status_code=403)
        try:
            data = await checked_form(request, row)
        except ValueError:
            return HTMLResponse('CSRF rejected. Reload /login.', status_code=403)
        if set(data) != {'csrf', 'username', 'password'}:
            return HTMLResponse('Unexpected login fields.', status_code=400)
        with sessions.lock:
            sessions.failures = [t for t in sessions.failures if t > clock() - 300]
            if len(sessions.failures) >= 5:
                return HTMLResponse('Too many login failures. Wait five minutes.', status_code=429)
            valid = verify_password(data['password'], password_hash)
            if not valid or not hmac.compare_digest(data['username'].encode(), username.encode()):
                sessions.failures.append(clock())
                return HTMLResponse('Invalid administrator credentials. Reload /login.', status_code=401)
            sessions.rows.pop(request.cookies.get(COOKIE), None)
            token, _ = sessions.mint(True)
        return cookie(RedirectResponse('/sessions', status_code=303), token)

    @app.post('/logout')
    async def logout(request: Request):
        row = identity(request)
        if row is None:
            return HTMLResponse('Admin login required.', status_code=401)
        try:
            await checked_form(request, row)
        except ValueError:
            return HTMLResponse('CSRF rejected.', status_code=403)
        with sessions.lock:
            sessions.rows.pop(request.cookies.get(COOKIE), None)
        response = RedirectResponse('/login', status_code=303)
        response.delete_cookie(COOKIE, path='/')
        return response

    def prerequisites(db, area, capabilities):
        tables = set(inspect(db.connection()).get_table_names())
        required = {
            'sessions': {'courses', 'class_schedules', 'class_sessions', 'student_groups', 'attendance'},
            'networks': {'network_policies', 'network_policy_events'},
            'wifi': {'wifi_classrooms', 'classroom_wifi_policies', 'classroom_wifi_policy_events'},
            'ble': {'wifi_classrooms', 'classroom_ble_policies', 'classroom_ble_policy_events'},
        }[area]
        if not required <= tables:
            raise ValueError('FEATURE_SCHEMA_UNAVAILABLE: validate the existing migration on an isolated restored copy first.')
        wifi_ready = capabilities.get('classroom_wifi') is True and {
            'wifi_classrooms', 'session_classroom_requirements', 'attempt_classroom_requirements', 'attendance_wifi_bindings'
        } <= tables
        return wifi_ready

    def page_body(db, area, row, capabilities):
        from models import Course, ClassSchedule, Student
        from modules.classroom_wifi.models import Classroom
        from manual_sessions import list_sessions
        from modules.networks.models import NetworkPolicy
        from modules.classroom_wifi.policies import listing as wifi_list
        from modules.classroom_ble.policies import listing as ble_list
        csrf = row['csrf']
        wifi_ready = prerequisites(db, area, capabilities)
        if area == 'sessions':
            courses = [(c.course_code, c.course_code + ' — ' + c.course_name) for c in db.scalars(select(Course).join(ClassSchedule).distinct())]
            room_options = [('', 'No classroom Wi-Fi requirement')]
            if wifi_ready:
                room_options += [(c.classroom_id, c.name) for c in db.scalars(select(Classroom).order_by(Classroom.classroom_id))]
            detail = ('Leave Group ID blank if the class has only one group. Sessions end on the same day.'
                      if wifi_ready else 'Classroom Wi-Fi assignment is unavailable in this environment.')
            body = card('Create attendance session', detail,
                form('/actions/sessions', csrf, choice('course_code', 'Class', courses) +
                    field('group_id', 'Group ID', 'number', required=False) +
                    field('minutes', 'Duration (minutes)', 'number', 30) +
                    choice('classroom_id', 'Classroom', room_options), 'Create Session',
                    variant='primary', grid=True, action='create'))
            body += ('<section id="action-pin" class="pin-card" aria-labelledby="pin-title" hidden>'
                     '<div><h2 id="pin-title">Attendance PIN</h2>'
                     '<p id="pin-meta"></p><strong id="pin-value"></strong>'
                     '<p>Copy or share this PIN before leaving the page.</p></div>'
                     '<button id="copy-pin" class="button secondary" type="button">Copy PIN</button>'
                     '<span id="copy-status" role="status"></span></section>')
            rows = list_sessions(db, now=current_time(), timezone=timezone, include_all=True)

            def controls(r):
                if r['status'] != 'active':
                    return ''
                session_id = r['session_id']
                actions = ''
                if r['window_state'] == 'OPEN':
                    actions = form('/actions/sessions', csrf,
                        '<noscript><label><input type="checkbox" name="confirm" value="yes">'
                        ' Confirm that the current PIN will stop working</label></noscript>',
                        'Regenerate PIN', action='regenerate', session_id=session_id,
                        confirmation=('Regenerate PIN', f'The current PIN for session #{session_id} will stop working for new submissions.'))
                return actions + form('/actions/sessions', csrf, '', 'Close Session', action='close',
                    session_id=session_id, variant='danger-outline',
                    confirmation=('Close Session', f'Session #{session_id} will stop accepting attendance. Existing submissions will be kept.'))

            body += card('Session history', 'PINs are shown only after creation or regeneration.',
                '<div id="management-table">' + table(rows,
                    [('session_id', 'Session ID'), ('class_code', 'Class'), ('group_id', 'Group'),
                     ('window_state', 'Status'), ('expires_at', 'Expiry'),
                     ('attendance_count', 'Attendance Count')], controls) + '</div>')
            if simulation_only:
                return body  # Existing isolated operator roles have no student-data grant.
            # Read-only identifiers/status; no passwords, face data or device keys.
            students = [dict(id=sid, group=group, status=status) for sid, group, status in db.execute(
                select(Student.student_id, Student.group_id, Student.account_status)
                .order_by(Student.student_id).limit(100))]
            return body + card('Students (read-only)', 'Showing up to 100 student records.',
                table(students, [('id', 'Student ID'), ('group', 'Group'), ('status', 'Account status')]))
        if area == 'networks':
            rows = [dict(id=p.network_id, name=p.network_name, cidr=p.network_cidr, enabled=p.enabled)
                    for p in db.scalars(select(NetworkPolicy).order_by(NetworkPolicy.network_id))]
            detail = ('Add simulation CIDRs here. Other policies are read-only.'
                      if simulation_only else 'New CIDR policies are enabled immediately.')
            body = card('Add network policy', detail, form('/actions/networks', csrf,
                field('id', 'Policy ID') + field('name', 'Description') + field('cidr', 'IPv4 / IPv6 CIDR'),
                'Add Policy', variant='primary', grid=True, action='add'))
            columns = [('id', 'ID'), ('name', 'Name'), ('cidr', 'CIDR'), ('policy_state', 'Status')]
        else:
            rows = wifi_list(db, include_all=True) if area == 'wifi' else ble_list(db, include_all=True)
            rows = [dict(r, id=r['policy_id']) for r in rows]
            inputs = field('id', 'Policy ID') + field('classroom', 'Classroom ID')
            inputs += (field('bssid', 'Approved BSSID') + field('ssid', 'Optional SSID', required=False) if area == 'wifi' else
                       field('uuid', 'Approved service UUID') + field('label', 'Optional label', required=False) +
                       field('minimum_samples', 'Minimum samples', 'number', 5) + field('threshold', 'Experimental median threshold dBm', 'number', -65) +
                       field('max_age_seconds', 'Maximum sample age, seconds', 'number', 15))
            detail = ('New Wi-Fi policies are enabled immediately and apply when a session is assigned that classroom.'
                      if area == 'wifi' else 'Experimental. New policies are disabled and are NOT enforced by attendance.')
            body = card('Add Wi-Fi policy' if area == 'wifi' else 'Add beacon policy', detail,
                form('/actions/' + area, csrf, inputs, 'Add Policy', variant='primary', grid=True, action='add'))
            columns = [('id', 'ID'), ('classroom_id', 'Classroom'),
                       ('bssid', 'BSSID'), ('ssid', 'SSID'), ('policy_state', 'Status')] if area == 'wifi' else [
                       ('id', 'ID'), ('classroom_id', 'Classroom'), ('service_uuid', 'UUID'), ('minimum_samples', 'Samples'),
                       ('rssi_threshold', 'Threshold'), ('max_age_seconds', 'Age (s)'), ('policy_state', 'Status')]
        for policy in rows:
            policy['policy_state'] = ('Retired' if policy.get('retired') else
                                      'Enabled' if policy['enabled'] else 'Disabled')

        def controls(r):
            if r.get('retired') or (simulation_only and area == 'networks' and not r['name'].startswith('SIMULATION ONLY - ')):
                return 'Read only'
            action = 'disable' if r['enabled'] else 'enable'
            title = action.capitalize() + ' Policy'
            return form('/actions/' + area, csrf, '', action.capitalize(), action=action, id=r['id'],
                confirmation=(title, f'Apply this change to policy {r["id"]}?'),
                variant='danger-outline' if action == 'disable' else 'secondary')
        return body + card('Policies', 'Review the current policy status and available actions.',
            '<div id="management-table">' + table(rows, columns, controls) + '</div>')

    @app.get('/admin-testing.js')
    def panel_script():
        return Response(Path(__file__).with_name('admin_testing.js').read_text(encoding='utf-8'),
                        media_type='text/javascript')

    @app.get('/admin-testing.css')
    def panel_style():
        return Response(Path(__file__).with_name('admin_testing.css').read_text(encoding='utf-8'),
                        media_type='text/css')

    @app.get('/')
    def home():
        return RedirectResponse('/sessions', status_code=303)

    @app.get('/{area}')
    def page(area: str, request: Request):
        if area not in PAGES:
            return HTMLResponse('Not found.', status_code=404)
        row = identity(request)
        if row is None:
            return RedirectResponse('/login', status_code=303)
        try:
            capabilities = ready()
            with Session(engine) as db:
                body = page_body(db, area, row, capabilities)
            return document(PAGES[area],
                '<section id="management"><p id="action-status" role="status"></p>' + body +
                '<dialog id="confirmation" aria-labelledby="confirm-title" aria-describedby="confirm-detail">'
                '<h2 id="confirm-title"></h2><p id="confirm-detail"></p>'
                '<form method="dialog" class="dialog-actions"><button class="button secondary" value="cancel" autofocus>Cancel</button>'
                '<button class="button primary" value="confirm" id="confirm-button">Confirm</button></form>'
                '</dialog></section>', row['csrf'], description=PAGE_INTROS[area])
        except (ValueError, ManualTestGuardError) as exc:
            response = document(PAGES[area], '<p class="notice">' + text(exc) + '</p>', row['csrf'])
            response.status_code = 503
            return response
        except SQLAlchemyError:
            response = document('Database unavailable', '<p class="notice">Database/schema unavailable. No fallback target is used.</p>', row['csrf'])
            response.status_code = 503
            return response

    @app.post('/actions/{area}')
    async def mutate(area: str, request: Request):
        ajax = request.headers.get('accept') == 'application/json'

        def reply(message, status=200, *, csrf=None, pin=None):
            if ajax:
                payload = {'message': message}
                if csrf is not None:
                    payload['csrf'] = csrf
                if pin is not None:
                    payload['pin'] = {k: pin[k] for k in ('session_id', 'pin', 'expires_at')}
                return JSONResponse(payload, status_code=status)
            if csrf is None:
                return HTMLResponse(text(message), status_code=status)
            if status == 200 and pin is None:
                return RedirectResponse('/' + area, status_code=303)
            body = '<p>' + text(message) + '</p>'
            if pin is not None:
                body += f'<p class="notice">Session {text(pin["session_id"])} · PIN: <strong>{text(pin["pin"])}</strong>. Shown once. Expires {text(pin["expires_at"])}.</p>'
            response = document(PAGES[area], body + f'<p><a href="/{area}">Back to {PAGES[area]}</a></p>', csrf)
            response.status_code = status
            return response

        if area not in PAGES:
            return reply('Not found.', 404)
        row = identity(request)
        if row is None:
            return reply('Admin login required. Sign in again.', 401)
        try:
            data = await checked_form(request, row)
        except ValueError:
            return reply('CSRF rejected. Reload the page.', 403)
        try:
            capabilities = ready()
        except (ValueError, ManualTestGuardError, SQLAlchemyError):
            return reply('BACKEND_NOT_READY: check the configured backend and database identity.', 503)
        next_csrf = None
        try:
            with sessions.lock:  # Also makes consumed form tokens single-use across concurrent submissions.
                if data['csrf'] != row['csrf'] or sessions.lookup(request.cookies.get(COOKIE)) is not row:
                    return reply('Form already used or session expired. Reload.', 403)
                next_csrf = row['csrf'] = secrets.token_urlsafe(32)
                with Session(engine) as db, db.begin():
                    wifi_ready = prerequisites(db, area, capabilities)
                    result = perform(db, area, data, username, current_time(), timezone, wifi_ready,
                                     simulation_only=simulation_only, current_time=current_time)
            # Commit has succeeded before showing a generated PIN. Never store PIN in session/URL/flash/log.
            message = ('New PIN generated. The previous PIN is invalid for new submissions.'
                       if data['action'] == 'regenerate' else 'Saved successfully.')
            return reply(message, csrf=next_csrf, pin=result)
        except (ValueError, ManualTestGuardError) as exc:
            return reply(str(exc), 400, csrf=next_csrf)
        except SQLAlchemyError:
            return reply('Database operation failed and was rolled back.', 503, csrf=next_csrf)

    return app


def perform(db, area, data, actor, now, timezone, wifi_ready, *, simulation_only=True, current_time=None):
    """Whitelist forms; delegate every mutation to existing Python operators."""
    from manual_sessions import create_session, close_session, regenerate_pin
    from fyp_test import change_policy
    from modules.classroom_wifi.policies import change as wifi_change
    from modules.classroom_ble.policies import change as ble_change
    action = data.get('action')
    common = {'csrf', 'action'}
    allowed = {
        ('sessions', 'create'): {'course_code', 'group_id', 'minutes', 'classroom_id'},
        ('sessions', 'close'): {'session_id'},
        ('sessions', 'regenerate'): {'session_id', 'confirm'},
        ('networks', 'add'): {'id', 'name', 'cidr'},
        ('wifi', 'add'): {'id', 'classroom', 'bssid', 'ssid'},
        ('ble', 'add'): {'id', 'classroom', 'uuid', 'label', 'minimum_samples', 'threshold', 'max_age_seconds'},
    }
    if action in ('enable', 'disable') and area in ('networks', 'wifi', 'ble'):
        expected = {'id'}
    else:
        expected = allowed.get((area, action))
    if expected is None or set(data) != common | expected:
        raise ValueError('INVALID_FORM_FIELDS_OR_ACTION')
    if area == 'sessions':
        if action == 'regenerate':
            if data['confirm'] != 'yes':
                raise ValueError('PIN_CHANGE_CONFIRMATION_REQUIRED')
            return regenerate_pin(db, session_id=int(data['session_id']),
                                  current_time=current_time or (lambda: now), timezone=timezone)
        if action == 'close':
            close_session(db, session_id=int(data['session_id']), now=now, timezone=timezone)
        else:
            classroom = data['classroom_id'] or None
            if classroom:
                from modules.classroom_wifi.models import Classroom
                if not wifi_ready or db.get(Classroom, classroom) is None:
                    raise ValueError('CLASSROOM_UNAVAILABLE: select an existing integrated classroom.')
            return create_session(db, now=now, timezone=timezone, course_code=data['course_code'],
                group_id=int(data['group_id']) if data['group_id'] else None, minutes=int(data['minutes']), classroom_id=classroom)
    elif area == 'networks':
        if simulation_only:
            change_policy(db, action, identifier=data['id'], now=now, actor=actor,
                **({'cidr': data['cidr'], 'name': data['name']} if action == 'add' else {}))
        else:
            from modules.networks.models import NetworkPolicy
            from modules.networks.policies import put_policy
            current = db.get(NetworkPolicy, data['id'], with_for_update=True)
            if action == 'add' and current is not None:
                raise ValueError('POLICY_ALREADY_EXISTS')
            if action != 'add' and current is None:
                raise ValueError('POLICY_NOT_FOUND')
            put_policy(db, network_id=data['id'], actor=actor, now=now,
                name=data['name'] if action == 'add' else current.network_name,
                cidr=data['cidr'] if action == 'add' else current.network_cidr,
                enabled=action != 'disable')
    elif area == 'wifi':
        wifi_change(db, action, policy_id=data['id'], now=now, actor=actor,
            **({'classroom': data['classroom'], 'access_point': data['bssid'], 'network_name': data['ssid'] or None} if action == 'add' else {}))
    else:
        ble_change(db, action, policy_id=data['id'], now=now, actor=actor,
            **({'classroom': data['classroom'], 'service_uuid': data['uuid'], 'label': data['label'] or None,
                'minimum_samples': int(data['minimum_samples']), 'rssi_threshold': int(data['threshold']),
                'max_age_seconds': int(data['max_age_seconds'])} if action == 'add' else {}))
