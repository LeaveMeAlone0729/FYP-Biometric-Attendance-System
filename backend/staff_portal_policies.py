"""Policy screens for the staff workspace, using the existing audited operators."""
from sqlalchemy import inspect, select

from staff_portal_views import BASE, badge, csrf_input, e, empty, field, panel

POLICY_PAGES = {
    'networks': ('Network Policies', 'Manage the source networks approved for student attendance.'),
    'wifi': ('Classroom Wi-Fi', 'Manage classrooms and the access points approved for each room.'),
    'ble': ('Experimental BLE', 'Configure classroom beacons and review experimental check results.'),
}


def policy_form(area, csrf, body, *, action='add', identifier=None, label='Add policy'):
    hidden = csrf_input(csrf) + f'<input type="hidden" name="action" value="{action}">'
    if identifier is not None:
        hidden += f'<input type="hidden" name="id" value="{e(identifier)}">'
    confirm = (f' data-confirm="{e(label)} policy {e(identifier)}?"' if action != 'add' else '')
    return (f'<form method="post" action="{BASE}/actions/{area}" data-portal-action '
            f'class="{"policy-form" if action == "add" else "policy-row-form"}">{hidden}{body}'
            f'<button class="button {"primary" if action == "add" else "secondary"}" type="submit"{confirm}>{e(label)}</button></form>')


def policy_table(rows, columns, controls=None):
    head = ''.join(f'<th>{e(label)}</th>' for _, label in columns)
    if controls:
        head += '<th>ACTIONS</th>'
    content = ''
    for row in rows:
        content += '<tr>' + ''.join(f'<td>{badge(row[key]) if key == "policy_state" else e(row.get(key, "—"))}</td>' for key, _ in columns)
        if controls:
            content += '<td>' + controls(row) + '</td>'
        content += '</tr>'
    if not content:
        return empty('No records yet', 'New policies and check results will appear here.')
    return f'<div class="table-scroll"><table><thead><tr>{head}</tr></thead><tbody>{content}</tbody></table></div>'


def policy_page(db, area, *, csrf, role, now, simulation_only):
    """Render all prior policy controls; student verification is not changed here."""
    from modules.networks.models import NetworkPolicy
    from modules.classroom_wifi.models import Classroom
    from modules.classroom_wifi.policies import listing as wifi_list
    from modules.classroom_ble.policies import listing as ble_list

    tables = set(inspect(db.connection()).get_table_names())
    required = {
        'networks': {'network_policies', 'network_policy_events'},
        'wifi': {'wifi_classrooms', 'classroom_wifi_policies', 'classroom_wifi_policy_events'},
        'ble': {'wifi_classrooms', 'classroom_ble_policies', 'classroom_ble_policy_events'},
    }[area]
    if not required <= tables:
        raise ValueError('This feature requires its existing policy tables. Check the configured database migrations.')
    admin = role == 'admin'
    body = '' if admin else '<p class="notice">You can review policies here. Sign in as admin to add, enable, or disable a policy.</p>'
    inputs = field('id', 'Policy ID', extra='maxlength="64"')
    if area == 'networks':
        rows = [dict(id=p.network_id, name=p.network_name, cidr=p.network_cidr, enabled=p.enabled)
                for p in db.scalars(select(NetworkPolicy).order_by(NetworkPolicy.network_id))]
        inputs += field('name', 'Network description', extra='maxlength="70"' if simulation_only else 'maxlength="100"')
        inputs += field('cidr', 'IPv4 / IPv6 CIDR', extra='placeholder="e.g. 10.20.0.0/16" maxlength="45"')
        detail = ('Local mode creates simulation-labelled policies. Existing non-simulation policies remain read-only.'
                  if simulation_only else 'New network policies are enabled immediately. Changes are recorded in the audit history.')
        columns = [('id', 'POLICY ID'), ('name', 'DESCRIPTION'), ('cidr', 'CIDR'), ('policy_state', 'STATUS')]
        title = 'Add network policy'
    else:
        rows = [dict(row, id=row['policy_id']) for row in (wifi_list(db, include_all=True) if area == 'wifi' else ble_list(db, include_all=True))]
        inputs += field('classroom', 'Classroom ID', extra='maxlength="64" placeholder="e.g. K201"')
        if area == 'wifi':
            inputs += field('bssid', 'Approved BSSID', extra='maxlength="17" placeholder="10:22:33:44:55:66"')
            inputs += field('ssid', 'SSID (optional)', required=False, extra='maxlength="32"')
            detail = 'New Wi-Fi policies are enabled immediately. Select a classroom when creating a session to require its Wi-Fi check.'
            columns = [('id', 'POLICY ID'), ('classroom_id', 'CLASSROOM'), ('bssid', 'APPROVED BSSID'), ('ssid', 'SSID'), ('policy_state', 'STATUS')]
            title = 'Add Wi-Fi policy'
        else:
            inputs += field('uuid', 'Approved service UUID', extra='maxlength="36" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"')
            inputs += field('label', 'Beacon label (optional)', required=False, extra='maxlength="100"')
            inputs += field('minimum_samples', 'Minimum samples', 'number', 5, extra='min="3" max="50"')
            inputs += field('threshold', 'Median RSSI threshold (dBm)', 'number', -65, extra='min="-127" max="0"')
            inputs += field('max_age_seconds', 'Maximum sample age (seconds)', 'number', 15, extra='min="10" max="30"')
            detail = 'New beacons are disabled until enabled. BLE checks are experimental observations and do not authorize attendance.'
            columns = [('id', 'POLICY ID'), ('classroom_id', 'CLASSROOM'), ('service_uuid', 'SERVICE UUID'),
                       ('label', 'LABEL'), ('minimum_samples', 'SAMPLES'), ('rssi_threshold', 'RSSI'),
                       ('max_age_seconds', 'AGE (s)'), ('policy_state', 'STATUS'), ('last_observation', 'LAST SIGNED CHECK')]
            title = 'Add beacon policy'
            summaries = {}
            if 'classroom_ble_events' in tables:
                from admin_testing import ble_observation_summaries
                summaries = ble_observation_summaries(db, {row['classroom_id'] for row in rows})
            for row in rows:
                row['last_observation'] = summaries.get(row['classroom_id'], 'No signed check')
    if admin:
        body += panel(title, detail, policy_form(area, csrf, inputs))
    else:
        body += f'<p class="policy-description">{e(detail)}</p>'
    for row in rows:
        row['policy_state'] = 'Retired' if row.get('retired') else 'Enabled' if row['enabled'] else 'Disabled'

    def controls(row):
        if row.get('retired'):
            return '<span class="cell-sub">Retired</span>'
        if simulation_only and area == 'networks' and not row['name'].startswith('SIMULATION ONLY - '):
            return '<span class="cell-sub">Read only</span>'
        action = 'disable' if row['enabled'] else 'enable'
        return policy_form(area, csrf, '', action=action, identifier=row['id'], label=action.title())

    body += panel('Configured policies', f'{len(rows)} policies. Existing policy IDs, settings, and history are retained.',
                  policy_table(rows, columns, controls if admin else None))
    if area in ('wifi', 'ble'):
        rooms = [dict(id=room.classroom_id, name=room.name) for room in db.scalars(select(Classroom).order_by(Classroom.classroom_id))]
        body += panel('Classrooms', 'A classroom is added automatically when its first Wi-Fi or beacon policy is created.',
                      policy_table(rooms, [('id', 'CLASSROOM ID'), ('name', 'NAME')]))
    if area == 'ble':
        body += ble_results(db, tables, now)
    return '<div id="policy-content">' + body + '</div>'


def ble_results(db, tables, now):
    body = ''
    required = {'verification_challenges', 'attempt_classroom_requirements', 'classroom_ble_challenges',
                'classroom_ble_events', 'classroom_wifi_events', 'attendance_wifi_bindings'}
    if required <= tables:
        from modules.classroom_ble.shadow import recent_outcomes
        body += panel('Attendance BLE shadow results', 'Latest 50 classroom attempt snapshots. BLE has no effect on attendance.',
            policy_table(list(recent_outcomes(db, now)), [('attempt', 'ATTEMPT'), ('session', 'SESSION'),
                ('classroom', 'CLASSROOM'), ('occurred', 'LOCAL TIME'), ('result', 'BLE RESULT'), ('reason', 'REASON')]))
    else:
        body += panel('Attendance BLE shadow results', 'Results appear when the classroom observation tables are available.',
                      empty('No observation history available', 'No observation records have been changed.'))
    if 'classroom_ble_events' in tables:
        from modules.classroom_ble.diagnostic_mode import recent_test_outcomes
        body += panel('Temporary Network + BLE Tests', 'Recent diagnostic simulations. These tests do not record attendance.',
            policy_table(list(recent_test_outcomes(db)), [('session', 'SESSION'), ('classroom', 'CLASSROOM'),
                ('occurred', 'LOCAL TIME'), ('result', 'TEST RESULT'), ('reason', 'REASON')]))
    else:
        body += panel('Temporary Network + BLE Tests', 'Diagnostic results appear after the first recorded test.',
                      empty('No diagnostic history available', 'BLE remains experimental.'))
    return body
