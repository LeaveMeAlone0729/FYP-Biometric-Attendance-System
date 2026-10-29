"""Registration security and persistence; real signatures, synthetic biometrics."""
import base64
import json
import os
import secrets
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, inspect, select
from sqlalchemy.pool import StaticPool
from app import create_app
from config import Settings
from database import make_sessions
from demo import seed_demo
from models import AuthSession, Base, Student, Attendance
from modules.devices.migration import upgrade_device_schema
from modules.devices.models import DEVICE_TABLES, DeviceRegistrationChallenge, DeviceRegistrationEvent, RegisteredDevice
from security import hash_password
import test_workflow

PREFIX = "/api/v1/devices"


class DeviceRegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password("test-password")

    def make_engine(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
        return engine

    def setUp(self):
        self.engine = self.make_engine()
        Base.metadata.create_all(self.engine)
        self.sessions = make_sessions(self.engine)
        self.now = datetime(2026, 10, 30, 12)
        self.settings = replace(Settings(), demo_mode=True, biometric_key=Fernet.generate_key().decode())
        with self.sessions.begin() as db:
            seed_demo(db, self.now)
            for identifier in ("DEVICE001", "DEVICE002"):
                db.add(Student(student_id=identifier, group_id=1, name="Device Student",
                    email=identifier.lower()+"@example.test", password_hash=self.password_hash, created_at=self.now))
        self.app = create_app(self.settings, self.engine, test_workflow.SyntheticBiometrics(), lambda: self.now)
        self.client = TestClient(self.app)
        self.headers = self.login("DEVICE001")
        self.key = ec.generate_private_key(ec.SECP256R1())

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def login(self, identifier):
        response = self.client.post("/login", json={"student_id": identifier, "password": "test-password"})
        self.assertEqual(response.status_code, 200, response.text)
        return {"Authorization": "Bearer " + response.json()["access_token"]}

    def body(self, key=None):
        public = (key or self.key).public_key().public_bytes(serialization.Encoding.DER,
                    serialization.PublicFormat.SubjectPublicKeyInfo)
        return dict(public_key_spki=base64.b64encode(public).decode(), device_name="Test phone",
                    device_model="Android Test Model", platform="android")

    def begin(self, headers=None, body=None):
        return self.client.post(PREFIX+"/registration-challenges", headers=headers or self.headers,
                                json=body or self.body())

    def confirmation(self, challenge, key=None):
        signature = (key or self.key).sign(base64.b64decode(challenge["signing_payload"]), ec.ECDSA(hashes.SHA256()))
        return dict(registration_id=challenge["registration_id"], signature=base64.b64encode(signature).decode())

    def confirm(self, challenge, key=None, headers=None):
        return self.client.post(PREFIX+"/registrations", headers=headers or self.headers,
                                json=self.confirmation(challenge, key))

    def count(self, model):
        with self.sessions() as db:
            return db.scalar(select(func.count()).select_from(model))

    def test_success_persists_public_key_and_audit_without_attendance(self):
        self.assertIsNone(self.client.get(PREFIX+"/current", headers=self.headers).json()["device"])
        started = self.begin()
        self.assertEqual(started.status_code, 201, started.text)
        payload = json.loads(base64.b64decode(started.json()["signing_payload"]))
        self.assertEqual(payload["operation"], "device_registration")
        self.assertEqual(payload["student_id"], "DEVICE001")
        result = self.confirm(started.json())
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(result.json()["device"]["status"], "ACTIVE")
        self.assertNotIn("public_key_spki", result.json()["device"])
        self.assertEqual(self.count(RegisteredDevice), 1)
        self.assertEqual(self.count(Attendance), 0)
        self.assertEqual(self.count(DeviceRegistrationEvent), 2)
        with self.sessions() as db:
            device = db.scalar(select(RegisteredDevice))
            self.assertEqual(device.public_key_spki, self.body()["public_key_spki"])
            self.assertIsNotNone(db.scalar(select(DeviceRegistrationChallenge)).consumed_at)
        self.assertEqual(self.client.get(PREFIX+"/current", headers=self.headers).json()["device"], result.json()["device"])

    def test_all_routes_require_authentication(self):
        for response in (self.client.get(PREFIX+"/current"), self.client.post(PREFIX+"/registration-challenges", json=self.body()),
                self.client.post(PREFIX+"/registrations", json={"registration_id":"x"*43,"signature":"x"})):
            self.assertEqual(response.status_code, 401)

    def test_duplicate_does_not_replace_registered_key(self):
        challenge = self.begin().json()
        self.assertEqual(self.confirm(challenge).status_code, 201)
        response = self.begin(body=self.body(ec.generate_private_key(ec.SECP256R1())))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "DEVICE_ALREADY_REGISTERED")
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(RegisteredDevice)).public_key_spki, self.body()["public_key_spki"])

    def test_replay_is_rejected_and_logged(self):
        challenge = self.begin().json()
        self.assertEqual(self.confirm(challenge).status_code, 201)
        self.assertEqual(self.confirm(challenge).json()["code"], "CHALLENGE_CONSUMED")
        self.assertEqual(self.count(RegisteredDevice), 1)
        with self.sessions() as db:
            self.assertEqual(db.scalars(select(DeviceRegistrationEvent).order_by(DeviceRegistrationEvent.event_id)).all()[-1].code,
                             "CHALLENGE_CONSUMED")

    def test_expiry_consumes_challenge_and_preserves_failed_audit(self):
        challenge = self.begin().json()
        self.now += timedelta(seconds=120)
        response = self.confirm(challenge)
        self.assertEqual(response.status_code, 410)
        self.assertEqual(self.confirm(challenge).status_code, 409)
        self.assertEqual(self.count(RegisteredDevice), 0)
        self.assertEqual(self.count(DeviceRegistrationEvent), 3)

    def test_wrong_signature_consumes_nonce(self):
        challenge = self.begin().json()
        response = self.confirm(challenge, ec.generate_private_key(ec.SECP256R1()))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "INVALID_SIGNATURE")
        self.assertEqual(self.confirm(challenge).status_code, 409)
        self.assertEqual(self.count(RegisteredDevice), 0)

    def test_malformed_signature_is_denied(self):
        challenge = self.begin().json()
        data = self.confirmation(challenge); data["signature"] = "not base64!"
        self.assertEqual(self.client.post(PREFIX+"/registrations", headers=self.headers, json=data).status_code, 403)

    def test_challenge_cannot_cross_accounts_or_logins(self):
        challenge = self.begin().json()
        for headers in (self.login("DEVICE002"), self.login("DEVICE001")):
            self.assertEqual(self.confirm(challenge, headers=headers).status_code, 404)
        self.assertEqual(self.confirm(challenge).status_code, 201)
        self.assertIsNone(self.client.get(PREFIX+"/current", headers=self.login("DEVICE002")).json()["device"])

    def test_logout_prevents_confirmation(self):
        challenge = self.begin().json()
        self.assertEqual(self.client.post("/logout", headers=self.headers).status_code, 200)
        self.assertEqual(self.confirm(challenge).status_code, 401)

    def test_replaced_pending_challenge_cannot_be_confirmed(self):
        old = self.begin().json(); fresh = self.begin().json()
        self.assertEqual(self.confirm(old).status_code, 409)
        self.assertEqual(self.confirm(fresh).status_code, 201)

    def test_key_cannot_be_registered_to_another_account(self):
        challenge = self.begin().json(); self.confirm(challenge)
        response = self.begin(headers=self.login("DEVICE002"))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "KEY_ALREADY_REGISTERED")

    def test_invalid_key_and_wrong_curve_are_rejected(self):
        for key in (ec.generate_private_key(ec.SECP384R1()), rsa.generate_private_key(65537, 2048)):
            self.assertEqual(self.begin(body=self.body(key)).status_code, 422)
        body = self.body(); body["public_key_spki"] = "!"*64
        self.assertEqual(self.begin(body=body).status_code, 422)
        self.assertEqual(self.count(RegisteredDevice), 0)

    def test_client_flags_private_key_and_non_android_are_rejected(self):
        for field, value in (("student_id", "DEVICE002"), ("private_key", "secret"), ("device_verified", True), ("platform", "ios")):
            body = self.body(); body[field] = value
            self.assertEqual(self.begin(body=body).status_code, 422)

    def test_challenge_rate_limit(self):
        for _ in range(5): self.assertEqual(self.begin().status_code, 201)
        self.assertEqual(self.begin().status_code, 429)
        self.now += timedelta(minutes=5, seconds=1)
        self.assertEqual(self.begin().status_code, 201)

    def test_tampered_operation_payload_cannot_be_signed_instead(self):
        challenge = self.begin().json()
        payload = json.loads(base64.b64decode(challenge["signing_payload"]))
        payload["operation"] = "attendance_authorize"
        signature = self.key.sign(json.dumps(payload).encode(), ec.ECDSA(hashes.SHA256()))
        data = {"registration_id":challenge["registration_id"], "signature":base64.b64encode(signature).decode()}
        self.assertEqual(self.client.post(PREFIX+"/registrations", headers=self.headers, json=data).status_code, 403)

    def test_migration_is_additive_idempotent_and_preserves_existing_rows(self):
        engine = create_engine("sqlite://")
        device_names = {t.name for t in DEVICE_TABLES}
        Base.metadata.create_all(engine, tables=[t for t in Base.metadata.sorted_tables if t.name not in device_names])
        with make_sessions(engine).begin() as db:
            seed_demo(db, self.now)
            db.add(Student(student_id="PRESERVE", group_id=1, name="Existing", email="existing@example.test",
                password_hash="unchanged", face_encoding="encrypted-existing", created_at=self.now))
        self.assertEqual(set(upgrade_device_schema(engine)), device_names)
        self.assertEqual(upgrade_device_schema(engine), [])
        with make_sessions(engine)() as db:
            self.assertEqual(db.get(Student, "PRESERVE").face_encoding, "encrypted-existing")
            self.assertEqual(db.get(Student, "PRESERVE").password_hash, "unchanged")
        self.assertNotIn("device_hash", {c["name"] for c in inspect(engine).get_columns("students")})
        engine.dispose()


@unittest.skipUnless(os.getenv("ATTENDANCE_DEVICE_MYSQL_TESTS") == "1", "Opt-in: disposable MySQL registration concurrency schema.")
class MySQLDeviceConcurrencyTests(unittest.TestCase):
    def test_parallel_confirmation_and_shared_key_race(self):
        import mysql.connector
        from database import make_engine
        settings = Settings()
        schema = "attendance_device_test_" + secrets.token_hex(6)
        connection = mysql.connector.connect(host=settings.db_host, port=settings.db_port,
            user=settings.db_user, password=settings.db_password)
        harness = DeviceRegistrationTests()
        engine = None
        created = False
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4")
            created = True
            engine = make_engine(replace(settings, db_name=schema))
            harness.make_engine = lambda: engine
            harness.password_hash = hash_password("test-password")
            harness.setUp()
            challenge = harness.begin().json()
            data = harness.confirmation(challenge)
            def submit(_):
                client = TestClient(harness.app)
                try:
                    return client.post(PREFIX+"/registrations", headers=harness.headers, json=data).status_code
                finally:
                    client.close()
            with ThreadPoolExecutor(max_workers=6) as pool:
                statuses = list(pool.map(submit, range(6)))
            self.assertEqual(statuses.count(201), 1, statuses)
            self.assertEqual(statuses.count(409), 5, statuses)
            self.assertEqual(harness.count(RegisteredDevice), 1)
            # A second pair of accounts compete for a new public key.
            with harness.sessions.begin() as db:
                db.add(Student(student_id="DEVICE003", group_id=1, name="Third", email="third@example.test",
                    password_hash=harness.password_hash, created_at=harness.now))
            key = ec.generate_private_key(ec.SECP256R1())
            contenders = []
            for identifier in ("DEVICE002", "DEVICE003"):
                headers = harness.login(identifier)
                challenge = harness.begin(headers=headers, body=harness.body(key)).json()
                contenders.append((headers, harness.confirmation(challenge, key)))
            def compete(item):
                headers, body = item
                client = TestClient(harness.app)
                try:
                    return client.post(PREFIX+"/registrations", headers=headers, json=body).status_code
                finally:
                    client.close()
            with ThreadPoolExecutor(max_workers=2) as pool:
                statuses = list(pool.map(compete, contenders))
            self.assertEqual(sorted(statuses), [201, 409])
            self.assertEqual(harness.count(RegisteredDevice), 2)
            self.assertEqual(harness.count(Attendance), 0)
        finally:
            if hasattr(harness, "client"): harness.tearDown()
            elif engine is not None: engine.dispose()
            if created:
                # Only this randomly named schema, created above, can be removed.
                assert schema.startswith("attendance_device_test_") and len(schema) == 35
                with connection.cursor() as cursor: cursor.execute(f"DROP DATABASE `{schema}`")
            connection.close()
