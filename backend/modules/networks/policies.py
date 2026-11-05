"""Operator-only configuration; no policy mutation endpoint is exposed to students."""
import json,re
from sqlalchemy import select
from .cidr import canonical_cidr
from .models import NetworkPolicy,NetworkPolicyEvent

def put_policy(db,*,network_id,name,cidr,enabled,actor,now):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',network_id):raise ValueError('Invalid network ID')
    if not isinstance(name,str) or not 1<=len(name.strip())<=100:raise ValueError('Network name must contain 1 to 100 characters')
    if not isinstance(enabled,bool):raise ValueError('Enabled must be a boolean')
    if not isinstance(actor,str) or not 1<=len(actor)<=128:raise ValueError('A configuration operator is required')
    canonical=canonical_cidr(cidr)
    policy=db.scalar(select(NetworkPolicy).where(NetworkPolicy.network_id==network_id).with_for_update())
    def snapshot(p):return json.dumps(dict(network_name=p.network_name,network_cidr=p.network_cidr,enabled=p.enabled),sort_keys=True)
    previous=snapshot(policy) if policy else None
    if policy is None:
        policy=NetworkPolicy(network_id=network_id,network_name=name.strip(),network_cidr=canonical,enabled=enabled,created_at=now,updated_at=now)
        db.add(policy)
    else:
        policy.network_name=name.strip();policy.network_cidr=canonical;policy.enabled=enabled;policy.updated_at=now
    db.flush()
    db.add(NetworkPolicyEvent(network_id=network_id,actor=actor,action='CREATED' if previous is None else 'UPDATED',previous_value=previous,new_value=snapshot(policy),occurred_at=now))
    db.flush();return policy
