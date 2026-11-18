"""Server-rendered, dependency-free staff portal components."""
from datetime import datetime
from html import escape

BASE = '/portal'
NAV = [('dashboard', 'Overview', 'grid'), ('sessions', 'Attendance Sessions', 'calendar'),
       ('attendance', 'Take attendance', 'check'), ('students', 'Students', 'users'),
       ('networks', 'Network Policies', 'shield'), ('wifi', 'Classroom Wi-Fi', 'wifi'),
       ('ble', 'Experimental BLE', 'bluetooth')]
ICONS = {
    'grid': '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    'calendar': '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18M8 15h2M14 15h2"/>',
    'check': '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="m8 12 3 3 5-6"/>',
    'users': '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6M21 21v-3a6 6 0 0 0-4-5"/>',
    'arrow': '<path d="M5 12h14m-5-5 5 5-5 5"/>',
    'logout': '<path d="M9 4H4v16h5M10 12h11m-4-4 4 4-4 4"/>',
    'search': '<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
    'download': '<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>',
    'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    'shield': '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
    'wifi': '<path d="M2 8a16 16 0 0 1 20 0M5 12a11 11 0 0 1 14 0M8 16a6 6 0 0 1 8 0"/><circle cx="12" cy="20" r=".5"/>',
    'bluetooth': '<path d="m7 7 10 10-5 5V2l5 5L7 17"/>',
}


def e(value):
    return escape(str(value if value is not None else ''), quote=True)


def icon(name):
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>'


def badge(status):
    tone = {'Present': 'green', 'Late': 'green', 'Absent': 'red', 'OPEN': 'green',
            'CLOSED': 'gray', 'SCHEDULED': 'blue', 'EXPIRED': 'gray', 'active': 'green',
            'Enabled': 'green', 'Disabled': 'gray', 'Retired': 'gray'}.get(status, 'gray')
    return f'<span class="badge {tone}"><span></span>{e(status.replace("_", " ").title())}</span>'


def button(label, href, kind='secondary', symbol=None):
    return f'<a class="button {kind}" href="{e(href)}">{icon(symbol) if symbol else ""}{e(label)}</a>'


def empty(title, detail):
    return f'<div class="empty-state">{icon("calendar")}<h3>{e(title)}</h3><p>{e(detail)}</p></div>'


def metric(label, value, detail, symbol, tone='teal'):
    return f'<article class="metric"><div class="metric-label">{e(label)}<span class="metric-icon {tone}">{icon(symbol)}</span></div><strong>{e(value)}</strong><p>{e(detail)}</p></article>'


def panel(title, detail, body, action=''):
    return f'<section class="panel"><div class="panel-heading"><div><h2>{e(title)}</h2><p>{e(detail)}</p></div>{action}</div>{body}</section>'


def csrf_input(csrf):
    return f'<input type="hidden" name="csrf" value="{e(csrf)}">'


def field(name, label, kind='text', value='', required=True, extra=''):
    return f'<label>{e(label)}<input name="{e(name)}" type="{kind}" value="{e(value)}" {"required" if required else ""} {extra}></label>'


def select_field(name, label, options, selected=''):
    return f'<label>{e(label)}<select name="{e(name)}">' + ''.join(
        f'<option value="{e(value)}" {"selected" if str(value) == str(selected) else ""}>{e(text)}</option>'
        for value, text in options) + '</select></label>'


def document(title, body, *, active='dashboard', csrf=None, username='', role='admin', now=None, description='', action=''):
    date_text = now.strftime('%A, %d %B %Y') if now else ''
    nav = ''.join(f'<a href="{BASE}/{key}" {"aria-current=page" if key == active else ""}>{icon(symbol)}{label}</a>'
                  for key, label, symbol in NAV)
    shell = (f'<aside class="sidebar"><a class="brand" href="{BASE}/dashboard"><span class="brand-icon">{icon("check")}</span>'
             '<span>BioAttend<small>STAFF PORTAL</small></span></a><span class="nav-caption">WORKSPACE</span>'
             f'<nav aria-label="Main navigation">{nav}</nav><div class="sidebar-bottom">'
             '<p>Campus attendance management</p></div></aside>'
             f'<div class="workspace"><header class="topbar"><span>Workspace <span class="slash">/</span> {e(title)}</span>'
             '<span class="topbar-right"><span class="live-dot"></span>Local portal'
             f'<span class="avatar">{e(username[:1].upper())}</span><span class="staff-name">{e(username)}</span><span class="staff-role">{e(role.title())}</span>'
             f'<form action="{BASE}/logout" method="post">{csrf_input(csrf)}<button class="icon-button" title="Sign out" aria-label="Sign out">{icon("logout")}</button></form></span></header>'
             f'<main id="main-content"><div class="page-heading"><div><p class="eyebrow">{e(date_text)} · MALAYSIA TIME</p><h1>{e(title)}</h1>'
             f'<p class="page-description">{e(description)}</p></div><div class="heading-actions">{action}</div></div>'
             '<div id="action-status" class="notice" role="status" aria-live="polite" hidden></div>'
             f'{body}<footer class="page-footer"><span>BioAttend · Admin &amp; teacher workspace</span><span>Asia/Kuala_Lumpur · UTC+08:00</span></footer></main></div>')
    if csrf is None:
        shell = body
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(title)} · BioAttend</title><link rel="stylesheet" href="{BASE}/assets/portal.css">'
            f'<script src="{BASE}/assets/portal.js" defer></script></head><body><a class="skip-link" href="#main-content">Skip to content</a>{shell}</body></html>')


def login_page(csrf, error='', username=''):
    error_html = f'<p class="notice error" role="alert">{e(error)}</p>' if error else ''
    return document('Staff sign in', '<main class="login-layout" id="main-content"><section class="login-story">'
        f'<a class="brand" href="{BASE}/"><span class="brand-icon">{icon("check")}</span><span>BioAttend<small>STAFF PORTAL</small></span></a>'
        '<div class="login-story-content"><p class="eyebrow">LESS ADMIN. MORE TEACHING.</p><h1>A clearer picture<br>of every class.</h1>'
        '<p>Your classes, your students, and their attendance.<br>One place to keep everything on track.</p>'
        '<div class="login-preview"><div><span class="live-dot"></span> YOUR TEACHING WORKSPACE</div>'
        f'<p>{icon("calendar")}Manage class sessions</p><p>{icon("users")}Review your student roster</p><p>{icon("check")}Record attendance with confidence</p></div></div>'
        '<p class="login-footer">Campus attendance management · Built for your teaching day</p></section>'
        '<section class="login-form-side"><div class="login-form-wrap"><span class="login-kicker">ADMIN &amp; TEACHER ACCESS</span><h2>Welcome back.</h2>'
        '<p>Sign in with your admin or teacher account.</p>'
        + error_html +
        f'<form method="post" action="{BASE}/login" class="login-form">{csrf_input(csrf)}'
        + field('username', 'Username', value=username, extra='autocomplete="username" maxlength="40" autofocus')
        + field('password', 'Password', 'password', extra='autocomplete="current-password" maxlength="128"')
        + f'<button class="button primary" type="submit">Sign in to workspace {icon("arrow")}</button></form>'
        '<p class="login-help">Use a staff account for this FYP profile. Student accounts sign in through the mobile app.</p>'
        f'<div class="login-security">{icon("shield")} Local access · Protected staff session</div></div></section></main>')


def session_table(rows, *, csrf=None, controls=False):
    if not rows:
        return empty('No class sessions yet', 'Create a session to start taking attendance for an existing class.')
    body = ''
    for r in rows:
        session = r['session']
        correction = (f'Teacher edits until {r["edit_deadline"]:%d %b %H:%M}' if r.get('editable')
                      else 'Not started' if r['state'] == 'SCHEDULED' else 'Read only')
        actions = button('Open register', f'{BASE}/attendance?session_id={session.session_id}', symbol='arrow')
        if controls and session.status == 'active':
            actions += (f'<form action="{BASE}/actions/sessions" method="post" data-portal-action>'
                        f'{csrf_input(csrf)}<input type="hidden" name="session_id" value="{session.session_id}">')
            if r['state'] == 'OPEN':
                actions += '<button class="button text-button" name="action" value="regenerate" data-confirm="Replace the current attendance PIN?">New PIN</button>'
            actions += '<button class="button text-button danger" name="action" value="close" data-confirm="Close this session for student check-in?">Close</button></form>'
        body += (f'<tr><td><a href="{BASE}/attendance?session_id={session.session_id}"><strong>{e(r["code"])}</strong><span class="cell-sub">{e(r["name"])}</span></a><span class="cell-sub">Session #{session.session_id}</span></td>'
                 f'<td>{e(r["group"])}<span class="cell-sub">{e(r["lecturer"])}</span></td>'
                 f'<td>{session.session_date:%d %b %Y}<span class="cell-sub">{session.start_time:%H:%M} – {session.end_time:%H:%M} · {e(session.venue)}</span></td>'
                 f'<td>{badge(r["state"])}<span class="cell-sub">{e(correction)}</span></td><td><strong>{r["present"]}</strong><span class="cell-sub">of {r["total"]} students</span></td>'
                 f'<td><div class="row-actions">{actions}</div></td></tr>')
    return '<div class="table-scroll"><table><thead><tr><th>CLASS</th><th>GROUP / LECTURER</th><th>DATE &amp; TIME</th><th>SESSION</th><th>PRESENT</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>' + body + '</tbody></table></div>'


