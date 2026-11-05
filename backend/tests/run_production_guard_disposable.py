"""Operator-only guard acceptance on a NEW verified DB-Readiness copy, port 3311.

Requires the private copy/helper/manifest prepared in the readiness runbook.
Never accepts a production administrator URL or starts an HTTP listener.
"""
import argparse
import hashlib
import json
import secrets
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "backend"))
from cryptography.fernet import Fernet
from production_guard import ProductionProfile, StartupGuardError, create_guarded_engine, validate_startup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--disposable-root", required=True)
    args = parser.parse_args()
    root = Path(args.disposable_root).resolve(strict=True)
    assert root.is_relative_to(Path("C:/FYP/DB-Readiness"))
    assert not (root / "guard-acceptance-results.json").exists(), "Do not overwrite a completed rehearsal"
    manifest = json.loads((root / "source-copy-manifest.json").read_text())
    assert manifest["source"] == "C:\\FYP\\DB-Acceptance\\20261104-003620"
    for rel, value in manifest["files"].items():
        path = root / rel
        assert path.stat().st_size == value["bytes"] and hashlib.sha256(path.read_bytes()).hexdigest() == value["sha256"]
    sys.path.insert(0, str(root))
    import acceptance_support as db
    assert db.ROOT == root and db.PORT == 3311
    from modules.biometrics.templates import encrypt_encoding
    results = []
    engines = []
    server = None

    def rejected(name, action):
        try:
            action()
        except StartupGuardError:
            results.append(dict(case=name, result="PASS"))
        else:
            raise AssertionError("Guard accepted: " + name)

    def check(p):
        engine = create_guarded_engine(p)
        engines.append(engine)
        validate_startup(engine, p)
        return engine

    try:
        server = db.start()
        db.integrity("guard-before")
        key = Fernet.generate_key().decode()
        # Synthetic schema ONLY. The restored production schema is never updated.
        c = db.connect("fyp_prod_runtime", db.CASES)
        try:
            with c.cursor() as q:
                q.execute("UPDATE students SET face_encoding=%s WHERE face_encoding IS NOT NULL AND face_encoding <> ''", (encrypt_encoding([0.0] * 128, key),))
            c.commit()
        finally:
            c.close()
        p = ProductionProfile(db_host="127.0.0.1", db_port=3311, db_name=db.CASES,
                              db_user="fyp_prod_runtime", db_password=db.CREDS["fyp_prod_runtime"],
                              expected_datadir=str(root / "data"), expected_basedir=str(root / "runtime"),
                              expected_version="10.4.27-MariaDB", biometric_key=key,
                              biometric_key_sha256=hashlib.sha256(key.encode()).hexdigest(),
                              timezone="Asia/Kuala_Lumpur", session_hours=8, challenge_seconds=90,
                              face_threshold=0.45, demo_mode=False)
        engine = check(p)
        results.append(dict(case="real_server_exact_identity_grants_schema_and_template_decryption", result="PASS"))
        rejected("wrong_datadir", lambda: check(replace(p, expected_datadir=str(root / "wrong"))))
        rejected("wrong_basedir", lambda: check(replace(p, expected_basedir=str(root / "wrong-runtime"))))
        rejected("wrong_schema", lambda: check(replace(p, db_name=db.RECOVERED)))
        rejected("wrong_password", lambda: check(replace(p, db_password=secrets.token_urlsafe(40))))
        rejected("original_port_before_connect", lambda: replace(p, db_port=3306))
        rejected("root_before_connect", lambda: replace(p, db_user="root"))
        rejected("key_digest_mismatch", lambda: replace(p, biometric_key_sha256="0" * 64))
        wrong = Fernet.generate_key().decode()
        rejected("wrong_decryption_key_with_matching_profile_digest", lambda: check(replace(p, biometric_key=wrong, biometric_key_sha256=hashlib.sha256(wrong.encode()).hexdigest())))
        with engine.connect() as connection:
            connection.exec_driver_sql("USE information_schema")
        rejected("pooled_connection_schema_changed", lambda: validate_startup(engine, p))
        validate_startup(engine, p)
        results.append(dict(case="new_connection_recovers_after_bad_pool_connection_discarded", result="PASS"))
        admin = db.connect()
        try:
            with admin.cursor() as q:
                q.execute("GRANT DELETE ON fypacceptance.attendance TO 'fyp_prod_runtime'@'127.0.0.1'")
                try:
                    rejected("extra_runtime_delete_grant", lambda: check(p))
                finally:
                    q.execute("REVOKE DELETE ON fypacceptance.attendance FROM 'fyp_prod_runtime'@'127.0.0.1'")
                q.execute("REVOKE SELECT ON fypacceptance.courses FROM 'fyp_prod_runtime'@'127.0.0.1'")
                try:
                    rejected("missing_required_grant", lambda: check(p))
                finally:
                    q.execute("GRANT SELECT ON fypacceptance.courses TO 'fyp_prod_runtime'@'127.0.0.1'")
                q.execute("SET GLOBAL read_only=ON")
                try:
                    rejected("server_read_only", lambda: check(p))
                finally:
                    q.execute("SET GLOBAL read_only=OFF")
        finally:
            admin.close()
        validate_startup(engine, p)
        directory = PROJECT / ".work/recovery"
        directory.mkdir(parents=True, exist_ok=True)
        private = directory / ("disposable-guard-" + root.name + ".json")
        assert not private.exists()
        private.write_text(json.dumps(asdict(p)))
        try:
            command = [sys.executable, "-B", str(PROJECT / "backend/production_app.py"), "--profile", str(private), "--check-only"]
            completed = subprocess.run(command, capture_output=True, timeout=20)
            assert completed.returncode == 0 and completed.stdout.strip() == b"PRODUCTION_STARTUP_GUARD_PASS"
            results.append(dict(case="real_guarded_cli_check_only", result="PASS"))
            from production_app import create_production_app
            from fastapi.testclient import TestClient
            app = create_production_app(private)
            with TestClient(app) as client:
                response = client.get("/")
                assert response.status_code == 200 and response.json()["demo_mode"] is False
                assert client.get("/config").json()["required_frames"] == 3
            results.append(dict(case="real_guarded_app_lifespan_health_and_unchanged_liveness_config", result="PASS"))
        finally:
            private.unlink(missing_ok=True)
        db.integrity("guard-after")
        results.append(dict(case="all_26_baseline_tables_and_system_tables_preserved", result="PASS"))
    finally:
        for engine in engines:
            engine.dispose()
        if (root / "isolated.pid").exists():
            db.stop()
        if server:
            server.wait(timeout=15)
    outcome = dict(result="PASS", cases=results, passed=len(results), port=3311,
                   no_original_sql_connections=True, restored_table_hashes_match=True,
                   server_left_stopped=not (root / "isolated.pid").exists())
    (root / "guard-acceptance-results.json").write_text(json.dumps(outcome, indent=2))
    print(json.dumps(dict(result=outcome["result"], passed=len(results), server_left_stopped=outcome["server_left_stopped"])))


if __name__ == "__main__":
    main()
