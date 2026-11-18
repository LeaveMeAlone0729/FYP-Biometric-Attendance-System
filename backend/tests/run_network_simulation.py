"""Explicit isolated ASGI-source simulation. Never edits production or server config."""
import json,sys
from pathlib import Path
from dataclasses import replace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from models import Attendance
from security import hash_password
from test_network_verification import NetworkTests

h=NetworkTests();h.password_hash=hash_password('test-password');h.setUp()
try:
    assert h.f.engine.dialect.name=='sqlite','Simulation must use its isolated in-memory database'
    settings=replace(h.f.settings,db_name='isolated_network_simulation')
    h.f.app.state.context.settings=settings;h.f.app.state.settings=settings
    cases=[]
    def sample(name,source,expected,reason=None,headers=None):
        response=h.request(source,headers);assert response.status_code==200,response.text
        result=response.json();assert result['result']==expected,result
        if reason:assert result['reason_code']==reason,result
        cases.append(dict(case=name,**result))
    sample('missing policy','192.0.2.10','FAIL','NO_ENABLED_NETWORK_POLICY')
    h.policy();h.policy('sim-v6','2001:db8:1234::/48')
    sample('authorised simulated IPv4','192.0.2.10','PASS')
    sample('unauthorised simulated IPv4','198.51.100.10','FAIL','NETWORK_NOT_AUTHORIZED')
    sample('spoofed X-Forwarded-For ignored','198.51.100.10','FAIL','NETWORK_NOT_AUTHORIZED',{'X-Forwarded-For':'192.0.2.10'})
    sample('authorised simulated IPv6','2001:db8:1234::5','PASS')
    sample('unauthorised simulated IPv6','2001:db8:9876::5','FAIL','NETWORK_NOT_AUTHORIZED')
    sample('IPv4-mapped IPv6','::ffff:192.0.2.10','PASS')
    sample('USB-style loopback is not campus proof','127.0.0.1','FAIL','LOOPBACK_SOURCE_NOT_AUTHORIZED')
    with h.f.sessions.begin() as db:db.execute(text("UPDATE network_policies SET network_cidr='invalid-cidr' WHERE network_id='sim-v4'"))
    sample('invalid enabled policy blocks all matches','2001:db8:1234::5','FAIL','NETWORK_POLICY_INVALID')
    with h.f.sessions.begin() as db:db.execute(text('UPDATE network_policies SET enabled=0'))
    sample('disabled policies','192.0.2.10','FAIL','NO_ENABLED_NETWORK_POLICY')
    assert h.count(Attendance)==0
    evidence=dict(environment='isolated in-memory SQLite / controlled ASGI source IPs',actual_campus_network_tested=False,production_records_modified=False,attendance_inserts=0,cases=cases)
    output=Path(__file__).resolve().parents[2]/'.work/p4-network-simulation.json';output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(dict(result='PASS',cases=len(cases),evidence=str(output),attendance_inserts=0)))
finally:h.tearDown()
