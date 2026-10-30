"""Stage A permits two slots in storage, but never enables second enrollment."""
import os
import re
import secrets
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError
from config import Settings
from modules.devices.crypto import canonical_public_key
from modules.devices.models import RegisteredDevice, DeviceRegistrationChallenge
from modules.devices.two_device_migration import upgrade_two_device_schema, verify_guards
from models import Attendance
from security import digest, hash_password
import test_device_verification as verification

PREFIX = "/api/v1/devices"


class TwoDeviceStageATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash=hash_password("test-password")

    def setUp(self):
        self.fixture=verification.DeviceVerificationTests()
        self.fixture.password_hash=self.password_hash
        if hasattr(self,"engine_override"): self.fixture.engine_override=self.engine_override
        self.fixture.setUp()
        self.key2=ec.generate_private_key(ec.SECP256R1())
        self.public2,self.fingerprint2=canonical_public_key(self.fixture.fixture.body(self.key2)["public_key_spki"])

    def tearDown(self):
        self.fixture.tearDown()

    def second(self, identifier="tablet-2", slot=2, student="DEVICE001", fingerprint=None):
        return RegisteredDevice(device_id=identifier,student_id=student,slot_number=slot,
            public_key_spki=self.public2,public_key_fingerprint=fingerprint or self.fingerprint2,
            device_name="Tablet",device_model="Untrusted descriptive model",platform="android",
            status="ACTIVE",registered_at=self.fixture.fixture.now)

    def seed_second(self):
        # Direct fixture insertion only. There is intentionally no enrollment API for this.
        with self.fixture.sessions.begin() as db: db.add(self.second())

    def test_list_two_and_verify_each_key_independently(self):
        self.seed_second()
        response=self.fixture.client.get(PREFIX,headers=self.fixture.headers)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual([d["slot_number"] for d in response.json()["devices"]],[1,2])
        self.assertEqual(response.json()["active_count"],2)
        self.assertFalse(response.json()["additional_enrollment_enabled"])
        for fingerprint,key,identifier in ((self.fixture.fingerprint,self.fixture.key,self.fixture.device_id),
                                            (self.fingerprint2,self.key2,"tablet-2")):
            started=self.fixture.issue(fingerprint=fingerprint)
            self.assertEqual(started.status_code,201,started.text)
            self.assertEqual(started.json()["device_id"],identifier)
            result=self.fixture.confirm(started.json(),key=key)
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()["device_id"],identifier)
        self.assertEqual(self.fixture.fixture.count(Attendance),0)

    def test_fingerprint_alone_cannot_pass_for_other_key(self):
        self.seed_second()
        challenge=self.fixture.issue(fingerprint=self.fingerprint2).json()
        self.assertEqual(self.fixture.confirm(challenge,key=self.fixture.key).status_code,403)

    def test_ambiguous_legacy_current_fails_closed(self):
        self.seed_second()
        response=self.fixture.client.get(PREFIX+"/current",headers=self.fixture.headers)
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.json()["code"],"DEVICE_SELECTOR_REQUIRED")

    def test_stage_a_blocks_second_enrollment_and_even_old_pending_confirmation(self):
        # A stale initial-enrollment proof must not fill slot 2 after slot 1 is occupied.
        client=self.fixture.client; headers=self.fixture.headers
        response=self.fixture.fixture.begin(body=self.fixture.fixture.body(self.key2))
        self.assertEqual(response.status_code,409)
        with self.fixture.sessions.begin() as db:
            db.add(DeviceRegistrationChallenge(registration_id="old-initial-"+"x"*32,student_id="DEVICE001",
                auth_token_hash=digest(headers["Authorization"].split()[1]),public_key_spki=self.public2,
                public_key_fingerprint=self.fingerprint2,device_name="Candidate",device_model="Test",
                signing_payload="old proof",created_at=self.fixture.fixture.now,
                expires_at=self.fixture.fixture.now+timedelta(minutes=1)))
        import base64
        from cryptography.hazmat.primitives import hashes
        signature=base64.b64encode(self.key2.sign(b"old proof",ec.ECDSA(hashes.SHA256()))).decode()
        response=client.post(PREFIX+"/registrations",headers=headers,
            json={"registration_id":"old-initial-"+"x"*32,"signature":signature})
        self.assertEqual(response.status_code,409,response.text)
        self.assertEqual(self.fixture.fixture.count(RegisteredDevice),1)

    def test_third_slot_duplicate_slot_and_invalid_status_are_rejected(self):
        self.seed_second()
        for slot,status in ((3,"ACTIVE"),(1,"ACTIVE"),(2,"UNKNOWN")):
            with self.assertRaises(IntegrityError):
                with self.fixture.sessions.begin() as db:
                    device=self.second(identifier=secrets.token_hex(10),slot=slot,fingerprint=secrets.token_hex(32))
                    device.status=status; db.add(device)
        self.assertEqual(self.fixture.fixture.count(RegisteredDevice),2)

    def test_isolated_revocation_does_not_change_other_device(self):
        self.seed_second()
        with self.fixture.sessions.begin() as db: db.get(RegisteredDevice,self.fixture.device_id).status="REVOKED"
        result=self.fixture.confirm(self.fixture.issue(fingerprint=self.fingerprint2).json(),key=self.key2)
        self.assertEqual(result.status_code,200,result.text)
        with self.fixture.sessions() as db:
            self.assertEqual(db.get(RegisteredDevice,"tablet-2").status,"ACTIVE")
            self.assertIsNone(db.get(RegisteredDevice,self.fixture.device_id).active_slot)
        # Revocation history must not reopen unauthenticated initial enrollment.
        self.assertEqual(self.fixture.fixture.begin(body=self.fixture.fixture.body(self.key2)).status_code,409)

    def test_selector_is_owner_scoped_and_required(self):
        with self.fixture.sessions.begin() as db:
            db.add(self.second(identifier="foreign",slot=1,student="DEVICE002"))
        self.assertEqual(self.fixture.issue(fingerprint=self.fingerprint2).status_code,403)
        response=self.fixture.client.post(PREFIX+"/verification-challenges",headers=self.fixture.headers,
                                          json={"operation":"device_status"})
        self.assertEqual(response.status_code,422)

    def test_missing_local_key_audit_is_unbound_to_either_device(self):
        self.seed_second()
        response=self.fixture.client.post(PREFIX+"/verification-failures",headers=self.fixture.headers,
            json={"operation":"device_status","reason_code":"LOCAL_KEY_MISSING"})
        self.assertEqual(response.status_code,200,response.text)
        from modules.devices.verification_models import DeviceVerificationEvent
        with self.fixture.sessions() as db:
            event=db.scalar(select(DeviceVerificationEvent).order_by(DeviceVerificationEvent.event_id.desc()))
            self.assertEqual(event.result,"FAIL"); self.assertIsNone(event.device_id); self.assertIsNone(event.challenge_id)


@unittest.skipUnless(os.getenv("ATTENDANCE_DEVICE_MYSQL_TESTS")=="1","Opt-in disposable MariaDB Stage A races.")
class StageAMariaDBTests(unittest.TestCase):
    def test_constraints_selection_and_concurrent_signatures(self):
        import mysql.connector
        from database import make_engine
        settings=Settings(); schema="attendance_stagea_test_"+secrets.token_hex(6)
        connection=mysql.connector.connect(host=settings.db_host,port=settings.db_port,user=settings.db_user,password=settings.db_password)
        harness=TwoDeviceStageATests(); engine=None; created=False
        try:
            with connection.cursor() as q: q.execute(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4")
            created=True; engine=make_engine(replace(settings,db_name=schema))
            harness.engine_override=engine; harness.password_hash=hash_password("test-password"); harness.setUp()
            harness.seed_second()
            report=upgrade_two_device_schema(engine,release_legacy=True)
            self.assertTrue(report["enforcement_probes_passed"])
            self.assertEqual(report["steps"],[])
            f=harness.fixture
            calls=[]
            for fingerprint,key in ((f.fingerprint,f.key),(harness.fingerprint2,harness.key2)):
                challenge=f.issue(fingerprint=fingerprint).json()
                calls.extend([f.body(challenge,key)]*2)
            def submit(body):
                client=TestClient(f.fixture.app)
                try: return client.post(PREFIX+"/verifications",headers=f.headers,json=body).status_code
                finally: client.close()
            with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(submit,calls))
            self.assertEqual(sorted(results),[200,200,409,409])
            for slot in (1,2,3):
                with self.assertRaises(DBAPIError):
                    with f.sessions.begin() as db: db.add(harness.second(identifier="third-"+str(slot),slot=slot,fingerprint=secrets.token_hex(32)))
            self.assertEqual(f.fixture.count(RegisteredDevice),2)
            self.assertEqual(f.fixture.count(Attendance),0)
        finally:
            if hasattr(harness,"fixture"): harness.tearDown()
            elif engine is not None: engine.dispose()
            if created:
                assert re.fullmatch(r"attendance_stagea_test_[0-9a-f]{12}",schema)
                with connection.cursor() as q: q.execute(f"DROP DATABASE `{schema}`")
            connection.close()


    def test_legacy_migration_resumes_and_keeps_old_guard_when_new_check_is_wrong(self):
        import mysql.connector
        from database import make_engine
        from modules.devices.two_device_migration import legacy_indexes
        settings=Settings(); schema="attendance_stagea_test_"+secrets.token_hex(6)
        control=mysql.connector.connect(host=settings.db_host,port=settings.db_port,user=settings.db_user,password=settings.db_password)
        engine=None; created=False
        try:
            with control.cursor() as q: q.execute(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4")
            created=True; engine=make_engine(replace(settings,db_name=schema))
            with engine.connect() as db:
                db.exec_driver_sql("CREATE TABLE students (student_id VARCHAR(11) PRIMARY KEY)")
                db.exec_driver_sql("INSERT INTO students VALUES ('LEGACY')")
                db.exec_driver_sql("""CREATE TABLE registered_devices (
                    device_id VARCHAR(64) PRIMARY KEY, student_id VARCHAR(11) NOT NULL,
                    public_key_spki TEXT NOT NULL, public_key_fingerprint VARCHAR(64) NOT NULL,
                    device_name VARCHAR(100) NOT NULL, device_model VARCHAR(150) NOT NULL,
                    platform VARCHAR(20) NOT NULL,status VARCHAR(20) NOT NULL,registered_at DATETIME NOT NULL,
                    UNIQUE KEY student_id (student_id), UNIQUE KEY public_key_fingerprint (public_key_fingerprint),
                    FOREIGN KEY (student_id) REFERENCES students(student_id)) ENGINE=InnoDB""")
                db.exec_driver_sql("INSERT INTO registered_devices VALUES ('existing','LEGACY','unchanged-public-key',REPEAT('a',64),'Samsung','SM-A346E','android','ACTIVE','2026-10-30 03:16:59')")
                original=db.exec_driver_sql("SELECT device_id,public_key_spki,public_key_fingerprint,status,registered_at FROM registered_devices").all()
                # Simulate an interrupted/incorrect partial deployment. It must not
                # remove the original student-only guard until validation succeeds.
                db.exec_driver_sql("ALTER TABLE registered_devices ADD COLUMN slot_number SMALLINT NULL")
                db.exec_driver_sql("ALTER TABLE registered_devices ADD CONSTRAINT ck_device_slot CHECK(slot_number IN (1,2,3))")
                db.commit()
            with self.assertRaises(RuntimeError): upgrade_two_device_schema(engine,release_legacy=True)
            with engine.connect() as db:
                self.assertEqual(legacy_indexes(db),['student_id'])
                db.exec_driver_sql("ALTER TABLE registered_devices DROP CONSTRAINT ck_device_slot"); db.commit()
            prepared=upgrade_two_device_schema(engine,release_legacy=False)
            self.assertTrue(prepared['legacy_unique_retained'])
            finished=upgrade_two_device_schema(engine,release_legacy=True)
            self.assertFalse(finished['legacy_unique_retained'])
            self.assertEqual(upgrade_two_device_schema(engine,release_legacy=True)['steps'],[])
            with engine.connect() as db:
                self.assertEqual(original,db.exec_driver_sql("SELECT device_id,public_key_spki,public_key_fingerprint,status,registered_at FROM registered_devices").all())
                self.assertEqual(db.exec_driver_sql("SELECT slot_number,active_slot FROM registered_devices").one(),(1,1))
        finally:
            if engine is not None: engine.dispose()
            if created:
                assert re.fullmatch(r"attendance_stagea_test_[0-9a-f]{12}",schema)
                with control.cursor() as q: q.execute(f"DROP DATABASE `{schema}`")
            control.close()
