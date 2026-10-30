"""Phase 2 real ECDSA signatures, replay/session rules and isolated MySQL races."""
import base64
import json
import os
import re
import secrets
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from config import Settings
from database import make_sessions
from demo import seed_demo
from models import Base, Student, Attendance
from modules.devices.crypto import canonical_public_key
from modules.devices.models import RegisteredDevice
from modules.devices.verification_models import DeviceVerificationChallenge, DeviceVerificationEvent, VERIFICATION_TABLES
from modules.devices.verification_migration import upgrade_verification_schema
from security import hash_password
import test_device_registration as registration

PREFIX = "/api/v1/devices"


class DeviceVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password("test-password")

    def setUp(self):
        self.fixture = registration.DeviceRegistrationTests()
        self.fixture.password_hash = self.password_hash
        if hasattr(self, "engine_override"):
            self.fixture.make_engine = lambda: self.engine_override
        self.fixture.setUp()
        self.client, self.sessions, self.headers = self.fixture.client, self.fixture.sessions, self.fixture.headers
        self.key = self.fixture.key
        response = self.fixture.confirm(self.fixture.begin().json())
        self.assertEqual(response.status_code, 201, response.text)
        self.device_id = response.json()["device"]["device_id"]
        self.fingerprint = response.json()["device"]["public_key_fingerprint"]

    def tearDown(self):
        self.fixture.tearDown()

    def issue(self, headers=None, fingerprint=None):
        return self.client.post(PREFIX+"/verification-challenges", headers=headers or self.headers,
                                json={"operation":"device_status", "public_key_fingerprint":fingerprint or self.fingerprint})

    def body(self, challenge, key=None):
        signature = (key or self.key).sign(base64.b64decode(challenge["signing_payload"]), ec.ECDSA(hashes.SHA256()))
        return {"challenge_id":challenge["challenge_id"], "operation":"device_status",
                "signature":base64.b64encode(signature).decode()}

    def confirm(self, challenge, headers=None, key=None):
        return self.client.post(PREFIX+"/verifications", headers=headers or self.headers,
                                json=self.body(challenge, key))

    def test_pass_is_fresh_bound_and_never_attendance_authorization(self):
        first = self.issue(); self.assertEqual(first.status_code, 201, first.text)
        payload = json.loads(base64.b64decode(first.json()["signing_payload"]))
        self.assertEqual(payload["purpose"], "device_verification")
        self.assertEqual(payload["operation"], "device_status")
        self.assertEqual(payload["student_id"], "DEVICE001")
        self.assertEqual(payload["device_id"], self.device_id)
        response = self.confirm(first.json())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["result"], "PASS")
        self.assertFalse(response.json()["attendance_authorized"])
        second = self.issue().json()
        self.assertNotEqual(first.json()["challenge_id"], second["challenge_id"])
        self.assertEqual(self.confirm(second).status_code, 200)
        self.assertEqual(self.fixture.count(Attendance), 0)
        with self.sessions() as db:
            outcomes = db.scalars(select(DeviceVerificationEvent).where(DeviceVerificationEvent.result == "PASS")).all()
            self.assertEqual(len(outcomes), 2)
            self.assertTrue(all(event.code == "DEVICE_VERIFIED" for event in outcomes))

    def test_all_routes_require_authentication(self):
        for path, body in (("verification-challenges", {"operation":"device_status"}),
                ("verifications", {"operation":"device_status","challenge_id":"x"*43,"signature":"x"}),
                ("verification-failures", {"operation":"device_status","challenge_id":"x"*43,"reason_code":"LOCAL_KEY_MISSING"})):
            self.assertEqual(self.client.post(PREFIX+"/"+path, json=body).status_code, 401)

    def test_unregistered_student_gets_failed_audit(self):
        response = self.issue(headers=self.fixture.login("DEVICE002"))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "DEVICE_NOT_REGISTERED")
        with self.sessions() as db:
            event = db.scalar(select(DeviceVerificationEvent))
            self.assertEqual((event.student_id,event.result,event.code),("DEVICE002","FAIL","DEVICE_NOT_REGISTERED"))

    def test_invalid_signature_is_terminal_and_logged(self):
        challenge = self.issue().json()
        self.assertEqual(self.confirm(challenge, key=ec.generate_private_key(ec.SECP256R1())).status_code, 403)
        self.assertEqual(self.confirm(challenge).status_code, 409)
        with self.sessions() as db:
            saved = db.get(DeviceVerificationChallenge, challenge["challenge_id"])
            self.assertEqual((saved.result,saved.failure_code),("FAIL","INVALID_DEVICE_SIGNATURE"))

    def test_malformed_signature_is_rejected(self):
        data = self.body(self.issue().json()); data["signature"] = "not base64!"
        self.assertEqual(self.client.post(PREFIX+"/verifications",headers=self.headers,json=data).status_code,403)

    def test_replay_does_not_overwrite_original_pass(self):
        challenge = self.issue().json()
        self.assertEqual(self.confirm(challenge).status_code,200)
        self.assertEqual(self.confirm(challenge).json()["code"],"VERIFICATION_REPLAYED")
        with self.sessions() as db:
            self.assertEqual(db.get(DeviceVerificationChallenge,challenge["challenge_id"]).result,"PASS")
            events=db.scalars(select(DeviceVerificationEvent).order_by(DeviceVerificationEvent.event_id)).all()
            self.assertEqual(events[-1].result,"FAIL")

    def test_expiry_consumes_challenge(self):
        challenge=self.issue().json(); self.fixture.now+=timedelta(seconds=60)
        self.assertEqual(self.confirm(challenge).status_code,410)
        self.assertEqual(self.confirm(challenge).status_code,409)

    def test_signature_work_cannot_cross_deadline(self):
        challenge=self.issue().json()
        def slow(*args):
            self.fixture.now+=timedelta(seconds=61)
            return True
        with patch("modules.devices.verification_service.verify_signature",side_effect=slow):
            self.assertEqual(self.confirm(challenge).status_code,410)

    def test_challenge_cannot_cross_account_or_login(self):
        challenge=self.issue().json()
        for headers in (self.fixture.login("DEVICE002"),self.fixture.login("DEVICE001")):
            self.assertEqual(self.confirm(challenge,headers=headers).status_code,404)
        self.assertEqual(self.confirm(challenge).status_code,200)

    def test_logout_blocks_verification(self):
        challenge=self.issue().json()
        self.client.post("/logout",headers=self.headers)
        self.assertEqual(self.confirm(challenge).status_code,401)

    def test_non_active_device_denied_at_issuance_and_confirmation(self):
        challenge=self.issue().json()
        with self.sessions.begin() as db: db.get(RegisteredDevice,self.device_id).status="REVOKED"
        self.assertEqual(self.issue().json()["code"],"DEVICE_NOT_ACTIVE")
        self.assertEqual(self.confirm(challenge).json()["code"],"DEVICE_NOT_ACTIVE")
        self.assertEqual(self.client.get(PREFIX+"/current",headers=self.headers).json()["device"]["status"],"REVOKED")

    def test_changed_registration_key_denied(self):
        challenge=self.issue().json()
        new_key=ec.generate_private_key(ec.SECP256R1())
        key,fingerprint=canonical_public_key(self.fixture.body(new_key)["public_key_spki"])
        with self.sessions.begin() as db:
            device=db.get(RegisteredDevice,self.device_id)
            device.public_key_spki=key; device.public_key_fingerprint=fingerprint
        self.assertEqual(self.confirm(challenge,key=new_key).json()["code"],"DEVICE_BINDING_CHANGED")

    def test_corrupt_registered_public_key_cannot_pass(self):
        challenge=self.issue().json()
        with self.sessions.begin() as db: db.get(RegisteredDevice,self.device_id).public_key_spki="invalid"
        self.assertEqual(self.confirm(challenge).json()["code"],"DEVICE_KEY_INVALID")

    def test_independent_concurrent_operations_do_not_supersede_each_other(self):
        first=self.issue().json(); second=self.issue().json()
        self.assertEqual(self.confirm(first).status_code,200)
        self.assertEqual(self.confirm(second).status_code,200)

    def test_unsupported_attendance_operation_and_pass_flags_rejected(self):
        for body in ({"operation":"attendance_start"},{"operation":"device_status","result":"PASS"},
                     {"operation":"device_status","student_id":"DEVICE002"},
                     {"operation":"device_status","attendance_attempt_id":"fake"}):
            self.assertEqual(self.client.post(PREFIX+"/verification-challenges",headers=self.headers,json=body).status_code,422)

    def test_operation_mismatch_is_denied(self):
        challenge=self.issue().json()
        with self.sessions.begin() as db: db.get(DeviceVerificationChallenge,challenge["challenge_id"]).operation="other"
        self.assertEqual(self.confirm(challenge).json()["code"],"OPERATION_MISMATCH")

    def test_signed_payload_tampering_cannot_pass(self):
        challenge=self.issue().json()
        payload=json.loads(base64.b64decode(challenge["signing_payload"]))
        payload["purpose"]="device_registration"
        signature=self.key.sign(json.dumps(payload).encode(),ec.ECDSA(hashes.SHA256()))
        body=self.body(challenge); body["signature"]=base64.b64encode(signature).decode()
        self.assertEqual(self.client.post(PREFIX+"/verifications",headers=self.headers,json=body).status_code,403)

    def test_client_key_failure_is_negative_untrusted_telemetry_only(self):
        challenge=self.issue().json()
        body={"challenge_id":challenge["challenge_id"],"operation":"device_status","reason_code":"LOCAL_KEY_MISSING"}
        response=self.client.post(PREFIX+"/verification-failures",headers=self.headers,json=body)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["result"],"FAIL")
        self.assertEqual(self.confirm(challenge).status_code,409)
        with self.sessions() as db:
            event=db.scalar(select(DeviceVerificationEvent).where(DeviceVerificationEvent.action=="client_failure"))
            self.assertEqual((event.source,event.result),("client","FAIL"))
        body["reason_code"]="PASS"
        self.assertEqual(self.client.post(PREFIX+"/verification-failures",headers=self.headers,json=body).status_code,422)

    def test_client_failure_cannot_cancel_another_login(self):
        challenge=self.issue().json()
        body={"challenge_id":challenge["challenge_id"],"operation":"device_status","reason_code":"KEYSTORE_UNAVAILABLE"}
        self.assertEqual(self.client.post(PREFIX+"/verification-failures",headers=self.fixture.login("DEVICE001"),json=body).status_code,404)
        self.assertEqual(self.confirm(challenge).status_code,200)

    def test_issuance_rate_limit(self):
        for _ in range(20): self.assertEqual(self.issue().status_code,201)
        self.assertEqual(self.issue().status_code,429)

    def test_migration_preserves_phase_one_public_key(self):
        engine=create_engine("sqlite://")
        excluded={t.name for t in VERIFICATION_TABLES}
        Base.metadata.create_all(engine,tables=[t for t in Base.metadata.sorted_tables if t.name not in excluded])
        with make_sessions(engine).begin() as db:
            seed_demo(db,self.fixture.now)
            db.add(Student(student_id="PRESERVE",group_id=1,name="Original",email="preserve@example.test",
                password_hash="original",created_at=self.fixture.now,face_encoding="encrypted-original"))
            db.flush()
            db.add(RegisteredDevice(device_id="original-device",student_id="PRESERVE",public_key_spki=self.fixture.body()["public_key_spki"],
                public_key_fingerprint="a"*64,device_name="Original",device_model="Samsung",status="ACTIVE",registered_at=self.fixture.now))
        self.assertEqual(set(upgrade_verification_schema(engine)),excluded)
        self.assertEqual(upgrade_verification_schema(engine),[])
        with make_sessions(engine)() as db:
            self.assertEqual(db.get(RegisteredDevice,"original-device").public_key_spki,self.fixture.body()["public_key_spki"])
            self.assertEqual(db.get(Student,"PRESERVE").face_encoding,"encrypted-original")
        engine.dispose()


@unittest.skipUnless(os.getenv("ATTENDANCE_DEVICE_MYSQL_TESTS")=="1","Opt-in disposable MySQL verification races.")
class MySQLVerificationConcurrencyTests(unittest.TestCase):
    def test_same_nonce_and_failure_vs_pass_races(self):
        import mysql.connector
        from database import make_engine
        settings=Settings(); schema="attendance_verify_test_"+secrets.token_hex(6)
        connection=mysql.connector.connect(host=settings.db_host,port=settings.db_port,user=settings.db_user,password=settings.db_password)
        harness=DeviceVerificationTests(); created=False; engine=None
        try:
            with connection.cursor() as cursor: cursor.execute(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4")
            created=True
            engine=make_engine(replace(settings,db_name=schema))
            harness.engine_override=engine; harness.password_hash=hash_password("test-password"); harness.setUp()
            challenge=harness.issue().json(); body=harness.body(challenge)
            def submit(item):
                route,data=item; client=TestClient(harness.fixture.app)
                try: return client.post(PREFIX+route,headers=harness.headers,json=data).status_code
                finally: client.close()
            with ThreadPoolExecutor(max_workers=6) as pool:
                results=list(pool.map(submit,[("/verifications",body)]*6))
            self.assertEqual(results.count(200),1,results)
            self.assertEqual(results.count(409),5,results)
            challenge=harness.issue().json()
            failure={"challenge_id":challenge["challenge_id"],"operation":"device_status","reason_code":"LOCAL_KEY_MISSING"}
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(submit,[("/verifications",harness.body(challenge)),("/verification-failures",failure)]))
            self.assertEqual(sorted(results),[200,409])
            with harness.sessions() as db:
                terminal=db.get(DeviceVerificationChallenge,challenge["challenge_id"])
                self.assertIn(terminal.result,("PASS","FAIL"))
            self.assertEqual(harness.fixture.count(Attendance),0)
        finally:
            if hasattr(harness,"fixture"): harness.tearDown()
            elif engine is not None: engine.dispose()
            if created:
                assert re.fullmatch(r"attendance_verify_test_[0-9a-f]{12}",schema)
                with connection.cursor() as cursor: cursor.execute(f"DROP DATABASE `{schema}`")
            connection.close()
