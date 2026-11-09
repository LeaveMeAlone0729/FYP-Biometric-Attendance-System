"""Offline simulation-only policy management. Retirement never deletes evidence."""
import json
import re
from sqlalchemy import select
from .models import Classroom, WifiPolicy, WifiPolicyEvent


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', value):
        raise ValueError('INVALID_CLASSROOM_OR_POLICY_ID')
    return value


def bssid(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', value):
        raise ValueError('WIFI_EVIDENCE_MALFORMED')
    value = value.lower()
    if value in ('02:00:00:00:00:00', '00:00:00:00:00:00', 'ff:ff:ff:ff:ff:ff') or int(value[:2], 16) & 1:
        raise ValueError('WIFI_EVIDENCE_MALFORMED')
    return value


def ssid(value):
    if value is not None and (not isinstance(value, str) or not value.strip() or
            len(value.encode('utf-8')) > 32 or any(ord(c) < 32 for c in value)):
        raise ValueError('INVALID_SSID')
    return value


def listing(db, classroom=None, include_all=False):
    return [dict(policy_id=p.policy_id, classroom_id=p.classroom_id, bssid=p.bssid,
                 ssid=p.ssid, enabled=p.enabled, retired=p.retired_at is not None)
            for p in db.scalars(select(WifiPolicy).order_by(WifiPolicy.classroom_id, WifiPolicy.policy_id))
            if (classroom is None or classroom == p.classroom_id) and (include_all or p.retired_at is None)]


def change(db, action, *, policy_id, now, actor, classroom=None, access_point=None, network_name=None):
    identifier(policy_id)
    # Fixed parent lock ordering also serializes policy creation within a classroom.
    if action == 'add':
        identifier(classroom)
        access_point = bssid(access_point)
        network_name = ssid(network_name)
        room = db.scalar(select(Classroom).where(Classroom.classroom_id == classroom).with_for_update())
        if room is None:
            room = Classroom(classroom_id=classroom, name=classroom, created_at=now)
            db.add(room); db.flush()
    p = db.scalar(select(WifiPolicy).where(WifiPolicy.policy_id == policy_id).with_for_update())
    if action == 'add':
        if p is not None: raise ValueError('WIFI_POLICY_ALREADY_EXISTS')
        p = WifiPolicy(policy_id=policy_id, classroom_id=classroom, bssid=access_point,
                       ssid=network_name, enabled=True, created_at=now)
        db.add(p); db.flush()
    else:
        if p is None: raise ValueError('WIFI_POLICY_NOT_FOUND')
        if p.retired_at is not None: raise ValueError('WIFI_POLICY_RETIRED')
        if action not in ('enable', 'disable', 'retire'): raise ValueError('INVALID_POLICY_ACTION')
        p.enabled = action == 'enable'
        if action == 'retire': p.retired_at = now
    snapshot = dict(classroom_id=p.classroom_id, bssid=p.bssid, ssid=p.ssid,
                    enabled=p.enabled, retired=p.retired_at is not None)
    db.add(WifiPolicyEvent(policy_id=policy_id, actor=actor[:100], action=action.upper(),
                          snapshot=json.dumps(snapshot), occurred_at=now))
    return dict(policy_id=policy_id, **snapshot)
