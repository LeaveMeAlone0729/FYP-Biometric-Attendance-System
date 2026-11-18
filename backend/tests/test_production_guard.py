"""Offline guard tests: no MariaDB listener or production settings needed."""
import hashlib
import json
import os
import secrets
import subprocess
import sys
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.fernet import Fernet
from sqlalchemy.engine import URL
from production_guard import (ProductionProfile, StartupGuardError, ROOT, create_guarded_engine,
                              load_profile, required_grants, validate_grants,
                              validate_connection, validate_startup)


def profile(**changes):
    key = Fernet.generate_key().decode()
    values = dict(db_host="127.0.0.1", db_port=3311, db_name="fypguardtest", db_user="fyp_prod_runtime",
                  db_password=secrets.token_urlsafe(40), expected_datadir="C:/FYP/DB-Readiness/fixture/data",
                  expected_basedir="C:/FYP/DB-Readiness/fixture/runtime", expected_version="10.4.27-MariaDB",
                  biometric_key=key, biometric_key_sha256=hashlib.sha256(key.encode()).hexdigest(),
                  timezone="Asia/Kuala_Lumpur", session_hours=8, challenge_seconds=90,
                  face_threshold=0.45, demo_mode=False)
    return ProductionProfile(**{**values, **changes})


def grants(p):
    result = ["GRANT USAGE ON *.* TO `fyp_prod_runtime`@`127.0.0.1` IDENTIFIED BY PASSWORD '*PRIVATE_HASH'"]
    for table, privileges in required_grants().items():
        for verb in ("SELECT", "INSERT", "UPDATE"):
            columns = sorted(col for v, col in privileges if v == verb and col is not None)
            if (verb, None) in privileges:
                resource = verb
            elif columns:
                resource = verb + " (" + ", ".join("`" + col + "`" for col in columns) + ")"
            else:
                continue
            result.append(f"GRANT {resource} ON `{p.db_name}`.`{table}` TO `fyp_prod_runtime`@`127.0.0.1`")
    return result


class ProfileTests(unittest.TestCase):
    def test_explicit_profile_ignores_unsafe_inherited_environment(self):
        with patch.dict(os.environ, dict(DB_HOST="bad", DB_PORT="3306", DB_USER="root", DB_NAME="attendance_proposal_xampp", DB_PASSWORD="", DEMO_MODE="true", BIOMETRIC_KEY="bad")):
            p = profile()
            settings = p.settings()
            engine = create_guarded_engine(p)
            try:
                self.assertEqual(engine.url.port, 3311)
                self.assertEqual(settings.db_user, "fyp_prod_runtime")
                self.assertFalse(settings.demo_mode)
                self.assertEqual(settings.biometric_key, p.biometric_key)
            finally:
                engine.dispose()

    def test_unsafe_values_rejected_before_connection(self):
        cases = [dict(db_port=3306), dict(db_port=True), dict(db_host="localhost"), dict(db_host="0.0.0.0"),
                 dict(db_user="root"), dict(db_user="admin"), dict(db_password=""), dict(db_password="password" * 8),
                 dict(db_name="attendance_proposal_xampp"), dict(db_name="mysql"), dict(demo_mode=True),
                 dict(demo_mode=0), dict(expected_version="10.4.28-MariaDB"), dict(expected_datadir="C:/xampp/mysql/data"),
                 dict(expected_basedir="C:/FYP/DB-Backups/old/runtime"), dict(expected_datadir="relative/data"),
                 dict(expected_datadir="C:/FYP/../xampp/mysql/data"), dict(biometric_key_sha256="0" * 64),
                 dict(biometric_key="invalid"), dict(face_threshold=float("nan"))]
        for case in cases:
            with self.subTest(field=list(case)), patch("production_guard.create_engine") as create:
                with self.assertRaises(StartupGuardError):
                    profile(**case)
                create.assert_not_called()

    def test_profile_secrets_not_in_repr(self):
        p = profile()
        self.assertNotIn(p.biometric_key, repr(p))
        self.assertNotIn(p.db_password, repr(p))

    def test_private_profile_exact_fields_duplicates_and_paths(self):
        directory = ROOT / ".work/recovery"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / ("offline-" + secrets.token_hex(8) + ".json")
        p = profile()
        try:
            path.write_text(json.dumps(asdict(p)))
            self.assertEqual(load_profile(path), p)
            for raw in [json.dumps({**asdict(p), "extra": True}), "{}", '{"db_host":"127.0.0.1","db_host":"other"}', "not json"]:
                path.write_text(raw)
                with self.assertRaises(StartupGuardError):
                    load_profile(path)
        finally:
            path.unlink(missing_ok=True)
        with self.assertRaises(StartupGuardError):
            load_profile(ROOT / "backend/production-profile.example.json")

    def test_importing_guarded_entry_point_does_not_load_config_or_open_socket(self):
        code = "import sys; sys.addaudithook(lambda event,args: (_ for _ in ()).throw(AssertionError('connection forbidden')) if event=='socket.connect' else None); import production_app; assert 'config' not in sys.modules; assert 'app' not in sys.modules; assert 'application_factory' not in sys.modules"
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT / "backend", capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_cli_missing_profile_fails_without_database(self):
        from production_app import main
        with patch("production_app.create_guarded_engine") as create:
            with patch("sys.stderr"):
                self.assertEqual(main(["--profile", "absent.json", "--check-only"]), 1)
            create.assert_not_called()


class GrantTests(unittest.TestCase):
    def test_exact_reviewed_privileges_accepted(self):
        p = profile()
        validate_grants(grants(p), p)
        # MariaDB SHOW GRANTS leaves column identifiers unquoted.
        unquoted = []
        import re
        for grant in grants(p):
            unquoted.append(re.sub(r"\([^()]+\)", lambda m: m[0].replace("`", ""), grant))
        validate_grants(unquoted, p)
        self.assertEqual(len(required_grants()), 29)
        self.assertEqual(required_grants()['device_enrollment_revisions'], {('SELECT', None)})

    def test_broad_missing_role_and_cross_schema_grants_fail(self):
        p = profile()
        extras = ["GRANT ALL PRIVILEGES ON *.* TO `fyp_prod_runtime`@`127.0.0.1`",
                  "GRANT SELECT ON `other`.* TO `fyp_prod_runtime`@`127.0.0.1`",
                  f"GRANT DELETE ON `{p.db_name}`.`attendance` TO `fyp_prod_runtime`@`127.0.0.1`",
                  f"GRANT UPDATE ON `{p.db_name}`.`students` TO `fyp_prod_runtime`@`127.0.0.1`",
                    f"GRANT INSERT ON `{p.db_name}`.`device_enrollment_revisions` TO `fyp_prod_runtime`@`127.0.0.1`",
                    f"GRANT UPDATE ON `{p.db_name}`.`device_enrollment_revisions` TO `fyp_prod_runtime`@`127.0.0.1`",
                  "GRANT `admin` TO `fyp_prod_runtime`@`127.0.0.1`",
                  grants(p)[1] + " WITH GRANT OPTION", grants(p)[1].replace("127.0.0.1", "%")]
        for extra in extras:
            with self.subTest(kind=extra.split(" ON ")[0]):
                with self.assertRaises(StartupGuardError):
                    validate_grants(grants(p) + [extra], p)
        with self.assertRaises(StartupGuardError):
            validate_grants(grants(p)[:-1], p)


class ConnectionTests(unittest.TestCase):
    def identity(self, p):
        return [p.db_name, "fyp_prod_runtime@127.0.0.1", p.db_port, p.expected_datadir + "/", p.expected_basedir + "/", p.expected_version, 0, "127.0.0.1", 0, "OFF", "OFF", "OFF"]

    def raw(self, p, identity=None):
        raw = MagicMock()
        raw.cursor.return_value.fetchone.return_value = identity or self.identity(p)
        raw.cursor.return_value.fetchall.return_value = [(g,) for g in grants(p)]
        return raw

    def test_expected_server_only_read_statements(self):
        p = profile()
        raw = self.raw(p)
        validate_connection(raw, p)
        statements = [c.args[0] for c in raw.cursor.return_value.execute.call_args_list]
        self.assertEqual(len(statements), 2)
        self.assertTrue(statements[0].startswith("SELECT DATABASE()"))
        self.assertEqual(statements[1], "SHOW GRANTS")

    def test_all_identity_and_safety_mismatches_fail(self):
        p = profile()
        for index, value in enumerate(["wrong", "root@localhost", 3306, "C:/xampp/mysql/data", "C:/wrong/runtime", "10.5.0", 1, "0.0.0.0", 1, "ON", "BACKUP,QUICK", "BACKUP"]):
            identity = self.identity(p)
            identity[index] = value
            with self.subTest(index=index), self.assertRaises(StartupGuardError):
                validate_connection(self.raw(p, identity), p)

    def test_connector_errors_do_not_disclose_secrets(self):
        p = profile()
        raw = self.raw(p)
        raw.cursor.return_value.execute.side_effect = RuntimeError(p.db_password)
        with self.assertRaises(StartupGuardError) as error:
            validate_connection(raw, p)
        self.assertNotIn(p.db_password, str(error.exception))

    def test_url_override_rejected_before_connection(self):
        p = profile()
        engine = MagicMock()
        engine.url = URL.create("mysql+mysqlconnector", username="root", password="", host="127.0.0.1", port=3306, database="attendance_proposal_xampp")
        with self.assertRaises(StartupGuardError):
            validate_startup(engine, p)
        engine.connect.assert_not_called()

    def test_lifespan_rejects_before_requests_and_cleans_up(self):
        from application_factory import create_app
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        p = profile()
        engine = create_engine("sqlite://")
        bio = MagicMock()
        validator = MagicMock(side_effect=StartupGuardError("TEST_REJECTED"))
        app = create_app(p.settings(), engine=engine, biometrics=bio, startup_validator=validator)
        with self.assertRaises(StartupGuardError):
            with TestClient(app):
                self.fail("HTTP serving must not start")
        validator.assert_called_once()
        bio.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
