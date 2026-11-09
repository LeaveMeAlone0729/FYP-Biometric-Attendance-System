"""Server evaluates signed client observations, never RF attestation or attendance."""
import base64,hashlib,json,secrets,statistics
from datetime import timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select,func
from config import iso_time
from modules.devices.crypto import decode_base64,verify_signature
from modules.devices.service import DeviceRegistrationError
from modules.devices.verification_service import DeviceVerificationService
from .models import BleChallenge,BleEvent
from .policies import enabled,digest,describe,canonical_uuid

OPERATION='classroom_ble_verification'
MESSAGES={
 'BLE_APPROVED':'The reported beacon samples meet this experimental classroom policy. This is not proof of physical presence.',
 'BLE_BEACON_NOT_FOUND':'No approved classroom beacon was reported in the completed scan.',
 'BLE_SIGNAL_WEAK':'The reported median RSSI is below the experimental threshold.',
 'BLE_INSUFFICIENT_SAMPLES':'Too few distinct observations to evaluate this beacon reliably. Repeat a full scan.',
 'NO_ENABLED_BLE_POLICY':'No enabled BLE policy exists for this classroom. An operator must explicitly enable one.',
 'BLE_POLICY_CHANGED':'The classroom BLE policy changed. Request a new check.',
 'BLE_POLICY_INVALID':'The enabled BLE policy is invalid. Ask the test operator to review it.',
 'BLE_EVIDENCE_MALFORMED':'The BLE report is malformed or exceeds its bounds. Scan again.',
 'BLE_EVIDENCE_STALE':'BLE evidence is stale or predates this challenge. Scan again.',
 'BLE_EVIDENCE_FUTURE':'BLE timestamps are in the future. Check automatic date/time and scan again.',
 'BLE_EVIDENCE_REPLAYED':'This scan report was already submitted. Perform a new scan.',
 'BLE_DUPLICATE_OBSERVATION':'Repeated observation timestamps cannot count as separate RSSI samples.',
 'BLE_PERMISSION_REQUIRED':'Allow Nearby Devices and precise location before scanning.',
 'BLUETOOTH_OFF':'Bluetooth is OFF or its state is unavailable. Use the Android enable prompt.',
 'BLE_UNAVAILABLE':'The Bluetooth scanner was unavailable or failed. No classroom decision was confirmed.',
 'BLE_SCAN_INCOMPLETE':'The scan was stopped or did not complete a full window. Repeat the scan.',
 'BLE_CHALLENGE_NOT_FOUND':'The BLE challenge belongs to another account/login or does not exist.',
 'BLE_CHALLENGE_EXPIRED':'The BLE challenge expired. Start a new check.',
 'BLE_CHALLENGE_REPLAYED':'The BLE challenge was already used. Start a new check.',
 'INVALID_DEVICE_SIGNATURE':'The registered device signature is invalid.',
 'BLE_RATE_LIMITED':'Too many BLE checks. Wait one minute before retrying.',
}


class EvidenceError(ValueError):
    def __init__(self,code='BLE_EVIDENCE_MALFORMED'):self.code=code


def parse(encoded):
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise EvidenceError()
            result[k]=v
        return result
    try:
        raw=decode_base64(encoded)
        if len(raw)>4500:raise EvidenceError()
        value=json.loads(raw.decode('utf-8'),object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(EvidenceError()))
        fields={'scan_status','bluetooth_enabled','scan_permission','connect_permission','location_permission','location_enabled','scan_started_at_ms','scan_completed_at_ms','scan_duration_ms','beacons'}
        if not isinstance(value,dict) or set(value)!=fields:raise EvidenceError()
        for k in ('scan_status','scan_permission','connect_permission','location_permission'):
            if not isinstance(value[k],str) or len(value[k])>40:raise EvidenceError()
        for k in ('bluetooth_enabled','location_enabled'):
            if value[k] is not None and type(value[k]) is not bool:raise EvidenceError()
        for k in ('scan_started_at_ms','scan_completed_at_ms','scan_duration_ms'):
            if type(value[k]) is not int or value[k]<0:raise EvidenceError()
        if not 0<=value['scan_duration_ms']<=10000 or value['scan_completed_at_ms']<value['scan_started_at_ms'] or abs(value['scan_completed_at_ms']-value['scan_started_at_ms']-value['scan_duration_ms'])>1000:raise EvidenceError()
        beacons=value['beacons']
        if not isinstance(beacons,list) or len(beacons)>4:raise EvidenceError()
        seen=set();total=0
        for beacon in beacons:
            if not isinstance(beacon,dict) or set(beacon)!={'service_uuid','samples'}:raise EvidenceError()
            beacon['service_uuid']=canonical_uuid(beacon['service_uuid'])
            if beacon['service_uuid'] in seen:raise EvidenceError('BLE_DUPLICATE_OBSERVATION')
            seen.add(beacon['service_uuid']);samples=beacon['samples']
            if not isinstance(samples,list) or len(samples)>50:raise EvidenceError()
            previous=-1
            for sample in samples:
                if not isinstance(sample,dict) or set(sample)!={'offset_us','rssi_dbm'}:raise EvidenceError()
                offset=sample['offset_us'];rssi=sample['rssi_dbm']
                if type(offset) is not int or not 0<=offset<=value['scan_duration_ms']*1000 or type(rssi) is not int or not -127<=rssi<=126:raise EvidenceError()
                if offset<=previous:raise EvidenceError('BLE_DUPLICATE_OBSERVATION')
                previous=offset;total+=1
        if total>50:raise EvidenceError()
        beacons.sort(key=lambda b:b['service_uuid'])
        return raw.decode('utf-8'),value
    except EvidenceError:raise
    except (ValueError,TypeError,UnicodeError):raise EvidenceError()


class BleVerificationService:
    def __init__(self,context):self.context=context;self.devices=DeviceVerificationService(context)
    def ms(self,dt):return int(dt.replace(tzinfo=ZoneInfo(self.context.settings.timezone)).timestamp()*1000)
    def event(self,db,student,result,code,ch=None,policy=None,count=None,median=None):
        event=BleEvent(student_id=student.student_id,result=result,reason_code=code,
            challenge_id=ch.challenge_id if ch else None,classroom_id=ch.classroom_id if ch else None,
            device_id=ch.device_id if ch else None,evidence_hash=ch.evidence_hash if ch else None,
            matched_policy_id=policy.policy_id if policy else None,sample_count=count,
            median_rssi=str(median) if median is not None else None,occurred_at=self.context.now())
        db.add(event);return event
    def deny(self,db,student,code,ch=None,status=403):
        if ch is not None and ch.consumed_at is None:
            ch.consumed_at=self.context.now();ch.result='FAIL';ch.failure_code=code
        self.event(db,student,'FAIL',code,ch)
        raise DeviceRegistrationError(status,code,MESSAGES[code])
    def policies(self,db,classroom):
        rows=enabled(db,classroom)
        if len(rows)>8 or len({p.service_uuid for p in rows})>4:raise ValueError('too many enabled policies')
        for p in rows:
            canonical_uuid(p.service_uuid)
            if not (p.simulation_only and 3<=p.minimum_samples<=50 and -127<=p.rssi_threshold<=0 and 10<=p.max_age_seconds<=30):raise ValueError('invalid policy')
        return rows
    def begin(self,db,student,auth,data):
        student=self.devices.identity(db,student,auth,OPERATION)
        try:device=self.devices.device(db,student,OPERATION,fingerprint=data.public_key_fingerprint)
        except DeviceRegistrationError as exc:self.event(db,student,'FAIL',exc.code);raise
        try:rows=self.policies(db,data.classroom_id)
        except ValueError:self.deny(db,student,'BLE_POLICY_INVALID')
        if not rows:self.deny(db,student,'NO_ENABLED_BLE_POLICY',status=409)
        recent=db.scalar(select(func.count()).select_from(BleChallenge).where(BleChallenge.student_id==student.student_id,BleChallenge.created_at>self.context.now()-timedelta(minutes=1)))
        if recent>=20:self.deny(db,student,'BLE_RATE_LIMITED',status=429)
        now=self.context.now();expires=min(now+timedelta(seconds=45),auth.expires_at)
        identifier=secrets.token_urlsafe(32);policy_hash=digest(rows)
        payload=json.dumps(dict(version=1,operation=OPERATION,challenge_id=identifier,student_id=student.student_id,
            auth_session_hash=auth.token_hash,device_id=device.device_id,key_fingerprint=device.public_key_fingerprint,
            classroom_id=data.classroom_id,policy_hash=policy_hash,nonce=secrets.token_urlsafe(32),
            issued_at_ms=self.ms(now),expires_at_ms=self.ms(expires)),sort_keys=True,separators=(',',':'))
        ch=BleChallenge(challenge_id=identifier,student_id=student.student_id,auth_token_hash=auth.token_hash,
            device_id=device.device_id,key_fingerprint=device.public_key_fingerprint,classroom_id=data.classroom_id,
            operation=OPERATION,policy_hash=policy_hash,signing_payload=payload,created_at=now,expires_at=expires)
        db.add(ch);self.event(db,student,'ISSUED','BLE_CHALLENGE_ISSUED',ch)
        return dict(success=True,operation=OPERATION,challenge_id=identifier,classroom_id=data.classroom_id,
            device_id=device.device_id,public_key_fingerprint=device.public_key_fingerprint,
            signing_payload=base64.b64encode(payload.encode()).decode(),expires_at=iso_time(expires,self.context.settings),
            approved_policies=[describe(p) for p in rows],scan_window_ms=8000)

    def confirm(self,db,student,auth,data):
        student=self.devices.identity(db,student,auth,OPERATION)
        ch=db.scalar(select(BleChallenge).where(BleChallenge.challenge_id==data.challenge_id).with_for_update().execution_options(populate_existing=True))
        if ch is None or ch.student_id!=student.student_id or ch.auth_token_hash!=auth.token_hash:self.deny(db,student,'BLE_CHALLENGE_NOT_FOUND',status=404)
        if ch.consumed_at is not None:self.deny(db,student,'BLE_CHALLENGE_REPLAYED',ch,409)
        if ch.expires_at<=self.context.now():self.deny(db,student,'BLE_CHALLENGE_EXPIRED',ch,410)
        if ch.operation!=OPERATION:self.deny(db,student,'BLE_CHALLENGE_NOT_FOUND',ch)
        try:
            device=self.devices.device(db,student,OPERATION,fingerprint=ch.key_fingerprint)
            if device.device_id!=ch.device_id:raise DeviceRegistrationError(403,'DEVICE_BINDING_CHANGED','The registered device changed.')
        except DeviceRegistrationError as exc:
            ch.consumed_at=self.context.now();ch.result='FAIL';ch.failure_code=exc.code;self.event(db,student,'FAIL',exc.code,ch);raise
        try:text,e=parse(data.evidence_payload)
        except EvidenceError as exc:self.deny(db,student,exc.code,ch,422)
        if not verify_signature(device.public_key_spki,ch.signing_payload+'\n'+text,data.signature):self.deny(db,student,'INVALID_DEVICE_SIGNATURE',ch)
        if ch.expires_at<=self.context.now() or auth.expires_at<=self.context.now():self.deny(db,student,'BLE_CHALLENGE_EXPIRED',ch,410)
        value_hash=hashlib.sha256(json.dumps(e,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if db.scalar(select(BleChallenge.challenge_id).where(BleChallenge.student_id==student.student_id,BleChallenge.device_id==device.device_id,BleChallenge.evidence_hash==value_hash).limit(1)):
            self.deny(db,student,'BLE_EVIDENCE_REPLAYED',ch,409)
        ch.evidence_hash=value_hash
        result,code,policy,count,median=self.evaluate(db,ch,e)
        ch.consumed_at=self.context.now();ch.result=result;ch.failure_code=None if result=='PASS' else code
        event=self.event(db,student,result,code,ch,policy if result=='PASS' else None,count,median);db.flush()
        return dict(success=True,result=result,reason_code=code,message=MESSAGES[code],verification_id=event.event_id,
            challenge_id=ch.challenge_id,
            classroom_id=ch.classroom_id,device_id=device.device_id,operation=OPERATION,
            evidence_source='CLIENT_REPORTED_ANDROID_BLE',attendance_authorized=False,
            matched_policy_id=policy.policy_id if policy and result=='PASS' else None,
            evaluated_policy_id=policy.policy_id if policy else None,sample_count=count or 0,median_rssi_dbm=median,
            rssi_threshold=policy.rssi_threshold if policy else None,minimum_samples=policy.minimum_samples if policy else None,
            max_age_seconds=policy.max_age_seconds if policy else None,verified_at=iso_time(event.occurred_at,self.context.settings))

    def evaluate(self,db,ch,e):
        def verdict(result,code):return result,code,None,None,None
        now=self.ms(self.context.now());start=e['scan_started_at_ms'];end=e['scan_completed_at_ms']
        if end>now or start>now:return verdict('FAIL','BLE_EVIDENCE_FUTURE')
        if start<json.loads(ch.signing_payload)['issued_at_ms'] or now-start>30000:return verdict('FAIL','BLE_EVIDENCE_STALE')
        try:policies=self.policies(db,ch.classroom_id)
        except ValueError:return verdict('FAIL','BLE_POLICY_INVALID')
        if not policies:return verdict('FAIL','NO_ENABLED_BLE_POLICY')
        if digest(policies)!=ch.policy_hash:return verdict('FAIL','BLE_POLICY_CHANGED')
        if e['scan_permission'] not in ('GRANTED','LEGACY_LOCATION_REQUIRED') or e['connect_permission']!='GRANTED' or e['location_permission']!='PRECISE_GRANTED' or e['location_enabled'] is not True:return verdict('UNCERTAIN','BLE_PERMISSION_REQUIRED')
        if e['bluetooth_enabled'] is not True:return verdict('UNCERTAIN','BLUETOOTH_OFF')
        if e['scan_status'] in ('STOPPED','CANCELLED') or (e['scan_status']=='COMPLETE' and e['scan_duration_ms']<7000):return verdict('UNCERTAIN','BLE_SCAN_INCOMPLETE')
        if e['scan_status']!='COMPLETE':return verdict('UNCERTAIN','BLE_UNAVAILABLE')
        observations={b['service_uuid']:b['samples'] for b in e['beacons']}
        candidates=[]
        for p in policies:
            samples=observations.get(p.service_uuid)
            if not samples:continue
            count=len(samples);median=float(statistics.median(s['rssi_dbm'] for s in samples))
            if any(now-(start+s['offset_us']/1000)>p.max_age_seconds*1000 for s in samples):result,code='FAIL','BLE_EVIDENCE_STALE'
            elif count<p.minimum_samples:result,code='UNCERTAIN','BLE_INSUFFICIENT_SAMPLES'
            elif median<p.rssi_threshold:result,code='FAIL','BLE_SIGNAL_WEAK'
            else:result,code='PASS','BLE_APPROVED'
            candidates.append((result,code,p,count,median))
        if not candidates:return verdict('FAIL','BLE_BEACON_NOT_FOUND')
        return max(candidates,key=lambda c:({'PASS':2,'UNCERTAIN':1,'FAIL':0}[c[0]],c[4]))
