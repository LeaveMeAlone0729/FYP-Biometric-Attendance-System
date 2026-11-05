"""Fresh connection-bound diagnostics; never an attendance authorization grant."""
from sqlalchemy import select
from fastapi import HTTPException
from config import iso_time
from models import Student,AuthSession
from .cidr import connection_ip,parse_cidr
from .models import NetworkPolicy,NetworkVerificationEvent

MESSAGES={
 'NETWORK_AUTHORIZED':'The backend-observed source IP matches an enabled authorised network policy.',
 'NETWORK_NOT_AUTHORIZED':'This connection is outside the authorised network ranges. Connect through the configured simulation network and check again.',
 'NO_ENABLED_NETWORK_POLICY':'No enabled network policy is configured. Ask the project operator to configure the simulation policy.',
 'NETWORK_POLICY_INVALID':'An enabled network policy is invalid. Verification is blocked until the operator corrects it.',
 'LOOPBACK_SOURCE_NOT_AUTHORIZED':'The backend sees a localhost connection, which is not campus-network proof. USB ADB reverse may cause this. Use isolated simulation tests or a direct configured LAN connection.',
 'SOURCE_IP_MISSING':'The backend connection has no usable source IP. Network verification is unavailable.',
 'SOURCE_IP_INVALID':'The backend connection source IP is invalid. Network verification is blocked.',
 'SOURCE_IP_NOT_UNICAST':'The backend connection source is not a valid unicast address.',
}

class NetworkVerificationService:
    def __init__(self,context):self.context=context

    def verify(self,db,student,auth,scope,*,operation='network_diagnostic',attendance_attempt_id=None):
        # The later final writer must call this with its CURRENT Request.scope and
        # server-owned attempt ID in the SAME transaction. Never reuse a diagnostic PASS.
        if operation not in ('network_diagnostic','attendance_authorization'):
            raise ValueError('Unsupported server operation')
        if (operation=='attendance_authorization') != (isinstance(attendance_attempt_id,str) and 0<len(attendance_attempt_id)<=64):
            raise ValueError('Attendance network checks require an exact server-owned attempt ID')
        if operation=='network_diagnostic' and attendance_attempt_id is not None:raise ValueError('Diagnostic cannot bind an attendance attempt')
        current=db.scalar(select(Student).where(Student.student_id==student.student_id).with_for_update().execution_options(populate_existing=True))
        session=db.scalar(select(AuthSession).where(AuthSession.token_hash==auth.token_hash).with_for_update().execution_options(populate_existing=True))
        if (current is None or current.account_status!='active' or session is None
                or session.student_id!=current.student_id or session.expires_at<=self.context.now()):
            raise HTTPException(401,'Your login changed or expired. Sign in again.')
        address,reason=connection_ip(scope);matched=None
        # No headers, JSON IP fields, device metadata, SSID or location are read.
        if reason is None:
            policies=db.scalars(select(NetworkPolicy).where(NetworkPolicy.enabled==True).order_by(NetworkPolicy.network_id).with_for_update()).all()
            networks=[]
            if not policies:reason='NO_ENABLED_NETWORK_POLICY'
            else:
                for policy in policies:
                    try:network=parse_cidr(policy.network_cidr)
                    except (ValueError,TypeError):
                        reason='NETWORK_POLICY_INVALID';break
                    networks.append((policy,network))
                if reason is None:
                    matches=[(policy,network) for policy,network in networks if address.version==network.version and address in network]
                    if matches:
                        matched,_=sorted(matches,key=lambda item:(-item[1].prefixlen,item[0].network_id))[0]
                        reason='NETWORK_AUTHORIZED'
                    else:reason='NETWORK_NOT_AUTHORIZED'
        result='PASS' if matched is not None else 'FAIL'
        event=NetworkVerificationEvent(student_id=current.student_id,auth_token_hash=session.token_hash,
            operation=operation,attendance_attempt_id=attendance_attempt_id,source_ip=str(address) if address is not None else None,
            result=result,reason_code=reason,matched_policy_id=matched.network_id if matched else None,
            policy_cidr=matched.network_cidr if matched else None,policy_updated_at=matched.updated_at if matched else None,verified_at=self.context.now())
        db.add(event);db.flush()
        return dict(success=True,verification_id=event.verification_id,result=result,reason_code=reason,message=MESSAGES[reason],
            source_ip=event.source_ip,matched_policy_id=event.matched_policy_id,matched_policy_name=matched.network_name if matched else None,
            verified_at=iso_time(event.verified_at,self.context.settings),operation=operation,attendance_authorized=False)
