from database_compat import shared_read
import hashlib,json,re,uuid
from sqlalchemy import select
from modules.classroom_wifi.models import Classroom
from modules.classroom_wifi.policies import identifier
from .models import BlePolicy,BlePolicyEvent


def canonical_uuid(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',value):raise ValueError('BLE_UUID_INVALID')
    parsed=uuid.UUID(value)
    if not parsed.int:raise ValueError('BLE_UUID_INVALID')
    return str(parsed)


def describe(p):
    return dict(policy_id=p.policy_id,classroom_id=p.classroom_id,service_uuid=p.service_uuid,label=p.label,
        enabled=p.enabled,minimum_samples=p.minimum_samples,rssi_threshold=p.rssi_threshold,
        max_age_seconds=p.max_age_seconds,simulation_only=p.simulation_only,revision=p.revision,
        retired=p.retired_at is not None)


def listing(db,classroom=None,include_all=False):
    return [describe(p) for p in db.scalars(select(BlePolicy).order_by(BlePolicy.policy_id))
        if (classroom is None or classroom==p.classroom_id) and (include_all or p.retired_at is None)]


def enabled(db,classroom):
    return list(db.scalars(select(BlePolicy).where(BlePolicy.classroom_id==classroom,BlePolicy.enabled.is_(True),
        BlePolicy.retired_at.is_(None)).order_by(BlePolicy.policy_id).with_for_update(read=shared_read(db)).execution_options(populate_existing=True)))


def digest(policies):return hashlib.sha256(json.dumps([describe(p) for p in policies],sort_keys=True,separators=(',',':')).encode()).hexdigest()


def change(db,action,*,policy_id,now,actor,classroom=None,service_uuid=None,label=None,minimum_samples=5,rssi_threshold=-65,max_age_seconds=15):
    identifier(policy_id)
    if action=='add':
        identifier(classroom);service_uuid=canonical_uuid(service_uuid)
        if not (type(minimum_samples) is int and 3<=minimum_samples<=50 and type(rssi_threshold) is int and -127<=rssi_threshold<=0 and type(max_age_seconds) is int and 10<=max_age_seconds<=30):raise ValueError('BLE_POLICY_LIMITS_INVALID')
        if label is not None and (not isinstance(label,str) or not label.strip() or len(label)>100):raise ValueError('BLE_POLICY_LABEL_INVALID')
        room=db.get(Classroom,classroom,with_for_update=True)
        if room is None:db.add(Classroom(classroom_id=classroom,name=classroom,created_at=now));db.flush()
    p=db.get(BlePolicy,policy_id,with_for_update=True,populate_existing=True)
    if action=='add':
        if p is not None:raise ValueError('BLE_POLICY_ALREADY_EXISTS')
        p=BlePolicy(policy_id=policy_id,classroom_id=classroom,service_uuid=service_uuid,label=label,
            enabled=False,minimum_samples=minimum_samples,rssi_threshold=rssi_threshold,max_age_seconds=max_age_seconds,
            simulation_only=True,revision=1,created_at=now,updated_at=now)
        db.add(p)
    else:
        if p is None:raise ValueError('BLE_POLICY_NOT_FOUND')
        if p.retired_at is not None:raise ValueError('BLE_POLICY_REMOVED')
        if action not in ('enable','disable','remove'):raise ValueError('BLE_POLICY_ACTION_INVALID')
        p.enabled=action=='enable';p.revision+=1;p.updated_at=now
        if action=='remove':p.retired_at=now
    db.flush();snapshot=describe(p)
    db.add(BlePolicyEvent(policy_id=policy_id,actor=actor[:100],action=action.upper(),snapshot=json.dumps(snapshot),occurred_at=now))
    return snapshot
