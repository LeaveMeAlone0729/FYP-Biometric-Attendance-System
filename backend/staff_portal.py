"""Localhost staff web application mounted beside the student API on port 8000."""
import csv
import hmac
import io
import ipaddress
import json
import secrets
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from admin_testing import AdminSessions
from models import Attendance, ClassSchedule, ClassSession, Course, Student, StudentGroup, VerificationAttempt
from security import verify_password
from services.staff_attendance import (PRESENT_STATUSES, StaffAttendanceError, mark_attendance,
                                       save_class_register, require_staff_edit_window)
from services.attendance_timing import class_end, correction_deadline, finalize_due_attendance, staff_can_edit
from staff_portal_policies import POLICY_PAGES, policy_page
from staff_portal_views import (BASE, badge, button, csrf_input, document, e, empty, field,
                                icon, login_page, metric, panel, select_field,
                                session_table)

COOKIE = 'fyp_staff_portal'
ASSETS = Path(__file__).with_name('staff_portal_assets')


def session_rows(db, now, limit=100, session_date=None, offset=0):
    """Fetch counts in batches rather than querying per session/student."""
    query = (select(ClassSession, ClassSchedule, Course, StudentGroup)
        .join(ClassSchedule, ClassSession.schedule_id == ClassSchedule.schedule_id)
        .join(Course, ClassSchedule.course_code == Course.course_code)
        .join(StudentGroup, ClassSchedule.group_id == StudentGroup.group_id)
        .order_by(ClassSession.session_date.desc(), ClassSession.start_time.desc(), ClassSession.session_id.desc()))
    if session_date is not None:
        query = query.where(ClassSession.session_date == session_date)
    if limit is not None:
        query = query.limit(limit)
    if offset:
        query = query.offset(offset)
    rows = db.execute(query).all()
    ids = [s.session_id for s, *_ in rows]
    present = dict(db.execute(select(Attendance.session_id, func.count())
        .where(Attendance.session_id.in_(ids), Attendance.status.in_(PRESENT_STATUSES))
        .group_by(Attendance.session_id)).all()) if ids else {}
    totals = dict(db.execute(select(Student.group_id, func.count()).group_by(Student.group_id)).all())
    result = []
    for s, schedule, course, group in rows:
        state = ('CANCELLED' if s.status == 'cancelled' else 'CLOSED' if s.status != 'active' else
                 'EXPIRED' if datetime.combine(s.session_date, s.end_time) <= now else
                 'SCHEDULED' if datetime.combine(s.session_date, s.start_time) > now else 'OPEN')
        result.append(dict(session=s, code=course.course_code, name=course.course_name,
            group=group.group_name, lecturer=schedule.lecturer, state=state,
            present=present.get(s.session_id, 0), total=totals.get(schedule.group_id, 0),
            editable=staff_can_edit(s, now), edit_deadline=correction_deadline(s)))
    return result


def roster(db, session_id):
    session = db.get(ClassSession, session_id)
    if session is None:
        raise StaffAttendanceError('Class session not found.', 404)
    schedule = db.get(ClassSchedule, session.schedule_id)
    course = db.get(Course, schedule.course_code)
    group = db.get(StudentGroup, schedule.group_id)
    rows = db.execute(select(Student, Attendance, VerificationAttempt)
        .outerjoin(Attendance, (Attendance.student_id == Student.student_id) &
                   (Attendance.session_id == session_id))
        .outerjoin(VerificationAttempt, Attendance.verification_id == VerificationAttempt.verification_id)
        .where(Student.group_id == schedule.group_id).order_by(Student.name, Student.student_id)).all()
    return session, schedule, course, group, rows


def create_staff_portal(engine, *, credential_loader, ready, timezone='Asia/Kuala_Lumpur',
                        now=None, clock=time.monotonic, port=8000, local_default_accounts=False,
                        policy_simulation_only=True):
    if not 1024 <= port <= 65535:
        raise ValueError('An unprivileged localhost portal port is required.')
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    sessions = AdminSessions(clock)
    current_time = now or (lambda: datetime.now(ZoneInfo(timezone)).replace(tzinfo=None))

    @app.middleware('http')
    async def protect(request, call_next):
        try:
            local = ipaddress.ip_address(request.client.host).is_loopback
        except (ValueError, AttributeError):
            local = False
        host = request.headers.get('host', '').lower()
        if not local or host not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
            return HTMLResponse('The staff portal is available on the server laptop only.', status_code=403)
        if request.method == 'POST':
            if request.headers.get('origin') != 'http://' + host:
                return HTMLResponse('Origin rejected. Open the portal on this laptop.', status_code=403)
            if request.headers.get('content-type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                return HTMLResponse('Use a standard HTML form.', status_code=415)
            maximum_body = 524288 if request.url.path.endswith('/actions/attendance-register') else 8192
            if len(await request.body()) > maximum_body:
                return HTMLResponse('Form too large.', status_code=413)
        response = await call_next(request)
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'same-origin',
            'Content-Security-Policy': "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'self'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"})
        return response

    def identity(request):
        row = sessions.lookup(request.cookies.get(COOKIE))
        return row if row and row['admin'] else None

    def set_cookie(response, token):
        response.set_cookie(COOKIE, token, httponly=True, samesite='strict', max_age=1800, path=BASE)
        return response

    async def checked_form(request, row, repeated=()):
        data = await request.form(max_fields=5005 if repeated else 15)
        if any(len(data.getlist(k)) != 1 for k in data if k not in repeated) or not hmac.compare_digest(
                str(data.get('csrf', '')).encode(), row['csrf'].encode()):
            raise StaffAttendanceError('This form expired. Reload the page before trying again.', 403)
        result = dict(data)
        for key in repeated:
            result[key] = data.getlist(key)
        return result

    def page(title, body, row, **kwargs):
        return HTMLResponse(document(title, body, csrf=row['csrf'], username=row['username'],
                                     role=row['role'], now=current_time(), **kwargs))

    def error_page(row, error, status=503):
        return HTMLResponse(document('Unable to load this page', panel('Please try again', str(error),
            button('Back to overview', BASE + '/dashboard')), csrf=row['csrf'], username=row['username'], role=row['role'],
            now=current_time()), status_code=status)

    @app.get('/assets/{name}')
    def asset(name: str):
        if name not in ('portal.css', 'portal.js'):
            return Response(status_code=404)
        return Response((ASSETS / name).read_text(encoding='utf-8'),
                        media_type='text/css' if name.endswith('.css') else 'text/javascript')

    @app.get('/')
    def home(request: Request):
        return RedirectResponse(BASE + ('/dashboard' if identity(request) else '/login'), status_code=303)

    @app.get('/login')
    def sign_in(request: Request):
        if identity(request):
            return RedirectResponse(BASE + '/dashboard', status_code=303)
        token, row = sessions.mint()
        return set_cookie(HTMLResponse(login_page(row['csrf'])), token)

    @app.post('/login')
    async def authenticate(request: Request):
        row = sessions.lookup(request.cookies.get(COOKIE))
        if row is None:
            return HTMLResponse(login_page('', 'Your sign-in form expired. Reload this page.'), status_code=403)
        try:
            data = await checked_form(request, row)
            if set(data) != {'csrf', 'username', 'password'}:
                raise StaffAttendanceError('Unexpected sign-in fields.')
            if len(data['username']) > 40 or len(data['password']) > 128:
                raise StaffAttendanceError('Invalid staff credentials.', 401)
            with sessions.lock:
                sessions.failures = [t for t in sessions.failures if t > clock() - 300]
                if len(sessions.failures) >= 5:
                    raise StaffAttendanceError('Too many sign-in attempts. Wait five minutes.', 429)
                accounts = []
                if local_default_accounts:
                    from staff_accounts import default_local_accounts
                    accounts.extend(default_local_accounts())
                try:
                    existing = credential_loader()
                    if not any(account['username'] == existing['username'] for account in accounts):
                        accounts.append(dict(existing, role='admin'))
                except Exception:
                    if not accounts:
                        raise StaffAttendanceError('Staff credentials are not configured. Initialize the admin account for this FYP profile first.', 503) from None
                credentials = next((account for account in accounts if hmac.compare_digest(
                    data['username'].encode(), account['username'].encode())), None)
                # Verify a hash for unknown usernames too, keeping password-check cost similar.
                valid = verify_password(data['password'], (credentials or accounts[0])['password_hash'])
                if credentials is None or not valid:
                    sessions.failures.append(clock())
                    raise StaffAttendanceError('Incorrect username or password.', 401)
                sessions.rows.pop(request.cookies.get(COOKIE), None)
                token, authenticated = sessions.mint(True)
                authenticated['username'] = credentials['username']
                authenticated['role'] = credentials['role']
            return set_cookie(RedirectResponse(BASE + '/dashboard', status_code=303), token)
        except StaffAttendanceError as exc:
            return HTMLResponse(login_page(row['csrf'], str(exc)), status_code=exc.status)

    @app.post('/logout')
    async def sign_out(request: Request):
        row = identity(request)
        if row is None:
            return RedirectResponse(BASE + '/login', status_code=303)
        try:
            await checked_form(request, row)
        except StaffAttendanceError as exc:
            return HTMLResponse(e(exc), status_code=exc.status)
        with sessions.lock:
            sessions.rows.pop(request.cookies.get(COOKIE), None)
        response = RedirectResponse(BASE + '/login', status_code=303)
        response.delete_cookie(COOKIE, path=BASE)
        return response

    @app.get('/dashboard')
    def dashboard(request: Request):
        row = identity(request)
        if row is None:
            return RedirectResponse(BASE + '/login', status_code=303)
        try:
            ready()
            now = current_time()
            with Session(engine) as db:
                finalize_due_attendance(db, now=now, session_date=now.date(), limit=None)
                db.commit()
                today = session_rows(db, now, limit=None, session_date=now.date())
                student_count = db.scalar(select(func.count()).select_from(Student))
                counts = dict(db.execute(select(Attendance.status, func.count()).join(ClassSession)
                    .where(ClassSession.session_date == now.date()).group_by(Attendance.status)).all())
                present = sum(counts.get(s, 0) for s in PRESENT_STATUSES)
                absent = counts.get('Absent', 0)
                body = '<section class="metrics" aria-label="Today at a glance">' + ''.join([
                    metric("Today's sessions", len(today), f'{sum(r["state"] == "OPEN" for r in today)} accepting student check-ins', 'calendar'),
                    metric('Present today', present, 'Confirmed attendance records', 'check', 'green'),
                    metric('Absent today', absent, 'Automatic and staff records', 'clock', 'amber'),
                    metric('Total students', student_count, 'Across all student groups', 'users', 'blue'),
                ]) + '</section>'
                body += '<section class="welcome-banner"><div><p class="eyebrow">YOUR TEACHING DAY, IN VIEW</p><h2>Keep every student accounted for.</h2><p>Open a class roster to review check-ins or record attendance yourself.</p></div>'
                body += button('Take attendance', BASE + '/attendance', 'light', 'arrow') + '</section>'
                body += panel("Today's class sessions", 'Review your classes and jump straight into the register.',
                              session_table(today), button('All sessions', BASE + '/sessions', 'text-button', 'arrow'))
                audits = db.execute(select(VerificationAttempt, Student.name, Course.course_code)
                    .join(Student, VerificationAttempt.student_id == Student.student_id)
                    .join(ClassSession, VerificationAttempt.session_id == ClassSession.session_id)
                    .join(ClassSchedule, ClassSession.schedule_id == ClassSchedule.schedule_id)
                    .join(Course, ClassSchedule.course_code == Course.course_code)
                    .where(VerificationAttempt.stage == 'teacher_attendance')
                    .order_by(VerificationAttempt.verification_id.desc()).limit(6)).all()
                activity = ''.join(f'<li><span class="activity-icon">{icon("check")}</span><div><strong>{e(name)}</strong><p>{e(code)} · {e(a.failure_reason)}</p></div><time>{a.attempted_at:%d %b · %H:%M}</time></li>' for a, name, code in audits)
                body += panel('Recent staff activity', 'A traceable history of attendance decisions.',
                              f'<ul class="activity-list">{activity}</ul>' if audits else empty('A fresh start', 'Staff attendance changes will appear here with the reason and time.'))
            return page('Overview', body, row, description='A little clarity for your teaching day.',
                        action=button('Create session', BASE + '/sessions#create-session', 'primary', 'calendar'))
        except Exception as exc:
            if isinstance(exc, SQLAlchemyError):
                return error_page(row, 'The configured database is unavailable. No records were changed.')
            return error_page(row, 'The backend identity could not be verified. Check fyp-start and the active profile.')

    @app.get('/sessions')
    def class_sessions(request: Request, history_page: int = 1):
        row = identity(request)
        if row is None:
            return RedirectResponse(BASE + '/login', status_code=303)
        try:
            capabilities = ready()
            with Session(engine) as db:
                total = db.scalar(select(func.count()).select_from(ClassSession))
                pages = max(1, (total + 49) // 50)
                history_page = min(max(1, history_page), pages)
                courses = [(c.course_code, c.course_code + ' · ' + c.course_name)
                           for c in db.scalars(select(Course).join(ClassSchedule).distinct().order_by(Course.course_code))]
                groups = [('', 'Auto-select if one group')] + [(g.group_id, g.group_name) for g in db.scalars(select(StudentGroup).order_by(StudentGroup.group_name))]
                rooms = [('', 'No classroom Wi-Fi requirement')]
                if capabilities.get('classroom_wifi'):
                    from modules.classroom_wifi.models import Classroom
                    rooms += [(c.classroom_id, c.name) for c in db.scalars(select(Classroom).order_by(Classroom.name))]
                create = (f'<form id="create-session" method="post" action="{BASE}/actions/sessions" class="session-form" data-portal-action>'
                    f'{csrf_input(row["csrf"])}<input type="hidden" name="action" value="create">'
                    + select_field('course_code', 'Course', courses) + select_field('group_id', 'Student group', groups)
                    + field('minutes', 'Duration in minutes', 'number', 30, extra='min="1" max="1440"')
                    + select_field('classroom_id', 'Classroom', rooms)
                    + '<div class="form-footer"><p>Creates a session starting now. Share its PIN with students.</p><button class="button primary" type="submit">Create session</button></div></form>')
                body = panel('Start a class session', 'Choose an existing class and set the student check-in window.', create)
                body += '<section id="pin-notice" class="pin-notice" hidden><div><span class="eyebrow">SHARE WITH YOUR CLASS</span><h2>Attendance PIN</h2><p id="pin-meta"></p></div><strong id="pin-value"></strong><button class="button secondary" id="copy-pin" type="button">Copy PIN</button><span id="copy-status" role="status"></span></section>'
                navigation = '<div class="history-pagination">'
                if history_page > 1:
                    navigation += button('Previous', f'{BASE}/sessions?history_page={history_page - 1}#session-list')
                navigation += f'<span>Page {history_page} of {pages} · {total} sessions</span>'
                if history_page < pages:
                    navigation += button('Next', f'{BASE}/sessions?history_page={history_page + 1}#session-list')
                navigation += '</div>'
                body += '<div id="session-list">' + panel('Session history', 'All class sessions. Open any register to review its attendance.',
                    session_table(session_rows(db, current_time(), limit=50, offset=(history_page - 1) * 50),
                                  csrf=row['csrf'], controls=True) + navigation) + '</div>'
            return page('Attendance Sessions', body, row, active='sessions', description='Create sessions, share attendance PINs, and review class attendance.')
        except Exception:
            return error_page(row, 'Class sessions could not be loaded. Check the configured backend and database.')

    @app.get('/attendance')
    def take_attendance(request: Request, session_id: int | None = None):
        row = identity(request)
        if row is None:
            return RedirectResponse(BASE + '/login', status_code=303)
        if session_id is None:
            return RedirectResponse(BASE + '/sessions#session-list', status_code=303)
        try:
            ready()
            with Session(engine) as db:
                finalize_due_attendance(db, now=current_time(), session_id=session_id, limit=None)
                db.commit()
                body = '<div class="register-back">' + button('Back to class sessions', BASE + '/sessions#session-list') + '</div>'
                if session_id is not None:
                    session, schedule, course, group, rows = roster(db, session_id)
                    present = sum(a is not None and a.status in PRESENT_STATUSES for _, a, _ in rows)
                    absent = sum(a is not None and a.status == 'Absent' for _, a, _ in rows)
                    now = current_time()
                    deadline = correction_deadline(session)
                    editable = staff_can_edit(session, now)
                    deadline_iso = deadline.replace(tzinfo=ZoneInfo(timezone)).isoformat()
                    body += '<div id="register-content">'
                    body += '<section class="register-summary"><div><span class="eyebrow">' + e(course.course_code) + '</span>'
                    body += f'<h2>{e(course.course_name)}</h2><p>Session #{session_id} · {e(group.group_name)} · {e(schedule.lecturer)} · {session.session_date:%d %b %Y} · {session.start_time:%H:%M}–{session.end_time:%H:%M} · {e(session.venue)}</p></div>'
                    body += button('Export CSV', f'{BASE}/attendance/export?session_id={session_id}', 'secondary', 'download') + '</section>'
                    body += '<section class="metrics compact">' + ''.join([
                        metric('Students', len(rows), 'In this class group', 'users', 'blue'),
                        metric('Present', present, 'Includes biometric check-ins', 'check', 'green'),
                        metric('Absent', absent, 'Automatic or staff record', 'clock', 'amber'),
                        metric('Unmarked', len(rows) - present - absent, 'Awaiting an attendance record', 'calendar'),
                    ]) + '</section>'
                    if editable:
                        body += f'<p id="register-deadline" class="notice">Teacher corrections close at {deadline:%d %b %Y, %H:%M} ({e(timezone)}), two hours after class ends. Missing attendance becomes absent at {class_end(session):%H:%M}.</p>'
                    elif session.status == 'cancelled':
                        body += '<p class="notice">This session was cancelled. Its register is read-only.</p>'
                    elif now >= deadline:
                        body += f'<p class="notice">The two-hour correction window ended at {deadline:%d %b %Y, %H:%M} ({e(timezone)}). This register is read-only.</p>'
                    else:
                        body += '<p class="notice">This register is read-only until the class starts.</p>'
                    versions = {student.student_id: str(attendance.verification_id) if attendance else 'unmarked' for student, attendance, _ in rows}
                    body += f'<form id="register-form" class="panel" method="post" action="{BASE}/actions/attendance-register" data-portal-action data-edit-deadline="{deadline_iso}">'
                    body += csrf_input(row['csrf']) + f'<input type="hidden" name="session_id" value="{session_id}"><input type="hidden" name="roster" value="{e(json.dumps(versions))}">'
                    body += '<div class="roster-toolbar"><div><h2>Enrolled students</h2><p>Tick students who are present, then save the class register.</p></div>'
                    body += '<label class="search-box"><span class="sr-only">Search students</span>' + icon('search') + '<input id="roster-search" placeholder="Search name or student ID" type="search"></label></div>'
                    body += '<div class="register-filters" role="group" aria-label="Filter attendance"><button type="button" class="filter-button active" data-filter="All" aria-pressed="true">All students</button><button type="button" class="filter-button" data-filter="Present" aria-pressed="false">Present</button><button type="button" class="filter-button" data-filter="Absent" aria-pressed="false">Absent</button><button type="button" class="filter-button" data-filter="Unmarked" aria-pressed="false">Unmarked</button><span id="visible-count" role="status"></span></div>'
                    if editable and rows:
                        body += '<div class="register-selection"><span id="selected-count" aria-live="polite"></span><div data-register-tools hidden><button type="button" class="button text-button" data-tick-visible="true">Tick all visible</button><button type="button" class="button text-button" data-tick-visible="false">Untick all visible</button></div></div>'
                    table_rows = ''
                    for student, attendance, audit in rows:
                        status = attendance.status if attendance else 'Unmarked'
                        manual = audit is not None and audit.stage == 'teacher_attendance'
                        automatic = audit is not None and audit.stage == 'auto_absence'
                        checkbox = f'<input type="checkbox" name="present" value="{e(student.student_id)}" data-present-check {"checked" if status in PRESENT_STATUSES else ""} {"disabled" if not editable else ""} aria-label="Mark {e(student.name)} present">'
                        note = ('Automatic absence' if automatic else 'Teacher record' if manual else 'Biometric check-in') if attendance else 'No record yet'
                        table_rows += (f'<tr data-roster-row data-status="{e(status)}"><td><label class="student-checkbox">{checkbox}<span class="student-cell"><span class="student-avatar">{e(student.name[:1].upper())}</span><span><strong>{e(student.name)}</strong><span class="cell-sub">{e(student.student_id)}</span></span></span></label></td>'
                            f'<td>{badge(status)}</td><td>{note}<span class="cell-sub">{attendance.taken_at.strftime("%d %b · %H:%M") if attendance else "—"}</span></td>'
                            f'<td class="audit-note">{e(audit.failure_reason) if manual or automatic else "—"}</td></tr>')
                    body += '<div class="table-scroll"><table id="roster-table"><thead><tr><th scope="col">PRESENT / STUDENT</th><th scope="col">SAVED STATUS</th><th scope="col">RECORDED VIA</th><th scope="col">STAFF / SYSTEM NOTE</th></tr></thead><tbody>' + table_rows + '</tbody></table></div>'
                    body += f'<p id="roster-empty" class="empty-state" {"hidden" if rows else ""}>No students match this register or filter.</p>'
                    if editable and rows:
                        body += '<div class="register-savebar"><div><strong>Ticked = Present · Unticked = Absent</strong><p>Applies to the whole class, including students hidden by a search or filter. Nothing changes until you save.</p></div>'
                        body += field('reason', 'Class note (optional)', required=False, extra='maxlength="120" minlength="3" placeholder="e.g. Roll call taken in class"')
                        body += '<button class="button primary" type="submit">Save attendance</button></div>'
                    body += f'<div class="register-footnote">{icon("shield")}Staff changes are recorded with your account and note. Existing checked biometric records are retained.</div></form></div>'
            return page('Take attendance', body, row, active='attendance', description='One class register. Every student accounted for.')
        except StaffAttendanceError as exc:
            return error_page(row, exc, exc.status)
        except Exception:
            return error_page(row, 'The attendance register could not be loaded. Check the configured backend and database.')

    @app.get('/attendance/export')
    def export_attendance(request: Request, session_id: int):
        row = identity(request)
        if row is None:
            return RedirectResponse(BASE + '/login', status_code=303)
        try:
            ready()
            with Session(engine) as db:
                finalize_due_attendance(db, now=current_time(), session_id=session_id, limit=None)
                db.commit()
                session, schedule, course, group, rows = roster(db, session_id)
                stream = io.StringIO(newline='')
                writer = csv.writer(stream)
                writer.writerow(['Student ID', 'Name', 'Course', 'Group', 'Session date', 'Status', 'Recorded at', 'Source', 'Staff note'])
                def safe(value):
                    text = str(value or '')
                    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')) else text
                for student, attendance, audit in rows:
                    manual = audit is not None and audit.stage == 'teacher_attendance'
                    automatic = audit is not None and audit.stage == 'auto_absence'
                    writer.writerow([safe(v) for v in (student.student_id, student.name, course.course_code,
                        group.group_name, session.session_date.isoformat(), attendance.status if attendance else 'Unmarked',
                        attendance.taken_at.isoformat() if attendance else '',
                        'Automatic' if automatic else 'Teacher' if manual else 'Biometric' if attendance else '',
                        audit.failure_reason if manual or automatic else '')])
            return Response('\ufeff' + stream.getvalue(), media_type='text/csv; charset=utf-8',
                            headers={'Content-Disposition': f'attachment; filename="attendance-session-{session_id}.csv"'})
        except StaffAttendanceError as exc:
            return error_page(row, exc, exc.status)
        except Exception:
            return error_page(row, 'The attendance export could not be generated.')

    @app.get('/students')
    def students(request: Request, q: str = ''):
        row = identity(request)
        if row is None:
            return RedirectResponse(BASE + '/login', status_code=303)
        try:
            ready()
            q = q.strip()[:100]
            with Session(engine) as db:
                query = select(Student, StudentGroup).join(StudentGroup, Student.group_id == StudentGroup.group_id)
                if q:
                    query = query.where(or_(Student.name.contains(q, autoescape=True), Student.student_id.contains(q, autoescape=True), StudentGroup.group_name.contains(q, autoescape=True)))
                rows = db.execute(query.order_by(Student.name, Student.student_id).limit(200)).all()
                form = f'<form method="get" action="{BASE}/students" class="student-search">' + field('q', 'Find students', value=q, required=False, extra='placeholder="Name, student ID, or group" maxlength="100"') + '<button class="button secondary">Search</button></form>'
                entries = ''.join(f'<tr><td><div class="student-cell"><span class="student-avatar">{e(s.name[:1].upper())}</span><div><strong>{e(s.name)}</strong><span class="cell-sub">{e(s.student_id)}</span></div></div></td><td>{e(g.group_name)}</td><td>{e(s.email)}</td><td>{badge(s.account_status)}</td></tr>' for s, g in rows)
                body = panel('Student directory', f'Showing {len(rows)} students (up to 200). Search to narrow the list.', form + ('<div class="table-scroll"><table><thead><tr><th>STUDENT</th><th>GROUP</th><th>EMAIL</th><th>ACCOUNT</th></tr></thead><tbody>' + entries + '</tbody></table></div>' if rows else empty('No students found', 'Try a different name, student ID, or group.')))
            return page('Students', body, row, active='students', description='Find students and see the groups they belong to.')
        except Exception:
            return error_page(row, 'The student directory could not be loaded.')

    @app.get('/networks')
    @app.get('/wifi')
    @app.get('/ble')
    def policy_settings(request: Request):
        row = identity(request)
        if row is None:
            return RedirectResponse(BASE + '/login', status_code=303)
        area = request.url.path.rstrip('/').rsplit('/', 1)[-1]
        title, description = POLICY_PAGES[area]
        try:
            ready()
            with Session(engine) as db:
                body = policy_page(db, area, csrf=row['csrf'], role=row['role'], now=current_time(),
                                   simulation_only=policy_simulation_only)
            return page(title, body, row, active=area, description=description)
        except ValueError as exc:
            return error_page(row, exc)
        except Exception:
            return error_page(row, 'Policy data could not be loaded. Check the configured backend and database.')

    @app.post('/actions/{area}')
    async def action(area: str, request: Request):
        row = identity(request)
        ajax = request.headers.get('accept') == 'application/json'
        def reply(message, status=200, **extra):
            if ajax:
                return JSONResponse(dict(message=message, **extra), status_code=status)
            if status == 200:
                if extra.get('pin'):
                    pin = extra['pin']
                    return page('Attendance PIN', panel('Share this PIN', 'This PIN is shown only once.',
                        f'<p class="pin-display">{e(pin["pin"])}</p>' + button('Back to sessions', BASE + '/sessions')), row)
                return RedirectResponse(BASE + ('/attendance?session_id=' + str(extra['session_id']) if area in ('attendance', 'attendance-register') else '/' + area), status_code=303)
            return error_page(row, message, status) if row else HTMLResponse(e(message), status_code=status)
        if row is None:
            return reply('Your staff session expired. Sign in again.', 401)
        if area not in ('attendance', 'attendance-register', 'sessions', *POLICY_PAGES):
            return reply('Unknown action.', 404)
        if area in POLICY_PAGES and row['role'] != 'admin':
            return reply('An admin account is required to change policies.', 403)
        try:
            data = await checked_form(request, row, repeated=('present',) if area == 'attendance-register' else ())
        except StaffAttendanceError as exc:
            return reply(str(exc), exc.status)
        try:
            capabilities = await run_in_threadpool(ready)
        except Exception:
            return reply('Backend identity could not be verified. No changes were made.', 503)
        try:
            with sessions.lock:
                if data['csrf'] != row['csrf'] or sessions.lookup(request.cookies.get(COOKIE)) is not row:
                    raise StaffAttendanceError('This form was already submitted. Reload before trying again.', 403)
                row['csrf'] = secrets.token_urlsafe(32)
                with Session(engine) as db, db.begin():
                    if area == 'attendance-register':
                        if set(data) != {'csrf', 'session_id', 'roster', 'present', 'reason'}:
                            raise StaffAttendanceError('Unexpected class register fields.')
                        try:
                            versions = json.loads(data['roster'])
                        except (ValueError, TypeError):
                            raise StaffAttendanceError('The class register could not be read. Reload this session.') from None
                        result = save_class_register(db, session_id=int(data['session_id']), versions=versions,
                            present_ids=data['present'], reason=data['reason'], actor=row['username'], now=current_time())
                        payload = dict(session_id=int(data['session_id']), **result)
                        message = f'Attendance saved: {result["present"]} present, {result["absent"]} absent. {result["changed"]} records updated.'
                    elif area == 'attendance':
                        if set(data) != {'csrf', 'session_id', 'student_id', 'status', 'version', 'reason'}:
                            raise StaffAttendanceError('Unexpected attendance fields.')
                        changed = mark_attendance(db, session_id=int(data['session_id']), student_id=data['student_id'],
                            status=data['status'], reason=data['reason'], version=data['version'], actor=row['username'], now=current_time())
                        payload = dict(session_id=int(data['session_id']))
                        message = f'{data["student_id"]} marked {data["status"].lower()}.' if changed else 'This attendance status is already saved.'
                    elif area in POLICY_PAGES:
                        from admin_testing import perform
                        perform(db, area, data, row['username'], current_time(), timezone,
                                capabilities.get('classroom_wifi') is True,
                                simulation_only=policy_simulation_only, current_time=current_time)
                        payload = {}
                        message = 'Policy saved. The change has been recorded in the audit history.'
                    else:
                        from admin_testing import perform
                        # Reuse existing session validation, classroom assignment, and PIN logic.
                        data.setdefault('confirm', 'yes') if data.get('action') == 'regenerate' else None
                        result = perform(db, 'sessions', data, row['username'], current_time(), timezone,
                                         capabilities.get('classroom_wifi') is True, current_time=current_time)
                        payload = dict(pin={key: result[key] for key in ('session_id', 'pin', 'expires_at')}) if result and 'pin' in result else {}
                        message = {'create': 'Session created. Share the PIN with your class.', 'regenerate': 'New PIN generated. The previous PIN is no longer valid.', 'close': 'Session closed. Its attendance records have been kept.'}[data['action']]
                    if area in ('attendance', 'attendance-register'):
                        require_staff_edit_window(db.get(ClassSession, int(data['session_id'])), current_time())
            return reply(message, csrf=row['csrf'], **payload)
        except StaffAttendanceError as exc:
            return reply(str(exc), exc.status, csrf=row['csrf'])
        except (ValueError, OverflowError) as exc:
            return reply(str(exc) if area in POLICY_PAGES else 'Invalid form values. Check your class, group, and session details.', 400, csrf=row['csrf'])
        except SQLAlchemyError:
            return reply('The database operation failed and was rolled back. Reload to review the register.', 503, csrf=row['csrf'])
        except Exception as exc:
            from manual_android_test import ManualTestGuardError
            if isinstance(exc, ManualTestGuardError):
                return reply(str(exc), 400, csrf=row['csrf'])
            return reply('The operation could not be completed. Reload before trying again.', 503, csrf=row['csrf'])

    return app


def install_staff_portal(app, *, credential_loader, ready, local_default_accounts=False, policy_simulation_only=True):
    context = app.state.context
    app.state.staff_portal_enabled = True
    app.mount(BASE, create_staff_portal(context.engine, credential_loader=credential_loader,
        ready=ready, timezone=context.settings.timezone, now=context.now,
        local_default_accounts=local_default_accounts, policy_simulation_only=policy_simulation_only))
