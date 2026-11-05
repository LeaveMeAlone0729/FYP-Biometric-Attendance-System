"""Opt-in recovery launch policy. No environment loading, seeding or SQL writes."""
import hashlib
import hmac
import json
import ntpath
import re
from dataclasses import dataclass, field, fields
from pathlib import Path
from types import SimpleNamespace

from cryptography.fernet import Fernet
from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = "fyp_prod_runtime"


class StartupGuardError(RuntimeError):
    """Messages are fixed codes, never connection strings, grants or secrets."""


def deny(code):
    raise StartupGuardError(code) from None


def path_identity(value):
    return ntpath.normcase(ntpath.normpath(str(value).replace("/", "\\")))


@dataclass(frozen=True)
class ProductionProfile:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str = field(repr=False)
    expected_datadir: str
    expected_basedir: str
    expected_version: str
    biometric_key: str = field(repr=False)
    biometric_key_sha256: str = field(repr=False)
    timezone: str
    session_hours: int
    challenge_seconds: int
    face_threshold: float
    demo_mode: bool

    def __post_init__(self):
        if self.db_host != "127.0.0.1" or type(self.db_port) is not int or not 1024 <= self.db_port <= 65535 or self.db_port == 3306:
            deny("UNAPPROVED_DATABASE_ENDPOINT")
        if self.db_user != RUNTIME or not isinstance(self.db_name, str) or not re.fullmatch(r"fyp[a-z0-9_]{1,55}", self.db_name):
            deny("UNAPPROVED_DATABASE_ACCOUNT_OR_SCHEMA")
        if not isinstance(self.db_password, str) or len(self.db_password) < 32 or any(x in self.db_password.lower() for x in ("changeme", "replace", "example", "password")):
            deny("UNSAFE_RUNTIME_SECRET")
        for directory in (self.expected_datadir, self.expected_basedir):
            if not isinstance(directory, str) or not re.match(r"^[A-Za-z]:[/\\]", directory) or ".." in directory.replace("\\", "/").split("/"):
                deny("UNAPPROVED_DATABASE_DIRECTORY")
            targets = (path_identity(directory), path_identity(Path(directory).resolve()))
            for forbidden in ("C:/xampp/mysql", "C:/FYP/DB-Backups", "C:/FYP/DB-Acceptance", "C:/FYP/DB-Soak", "C:/FYP/DB-Clean-Rehearsal", "C:/FYP/DB-Rehearsal"):
                base = path_identity(forbidden)
                if any(target == base or target.startswith(base + "\\") for target in targets):
                    deny("PROTECTED_DATABASE_DIRECTORY")
        if path_identity(self.expected_datadir) == path_identity(self.expected_basedir):
            deny("DATABASE_DIRECTORIES_MUST_DIFFER")
        if self.expected_version != "10.4.27-MariaDB":
            deny("UNREVIEWED_DATABASE_VERSION")
        if self.demo_mode is not False:
            deny("DEMO_MODE_MUST_BE_DISABLED")
        if self.timezone != "Asia/Kuala_Lumpur" or type(self.session_hours) is not int or self.session_hours <= 0 or type(self.challenge_seconds) is not int or self.challenge_seconds <= 0 or type(self.face_threshold) not in (float, int) or not 0 < self.face_threshold < 1:
            deny("INVALID_APPLICATION_SETTINGS")
        try:
            Fernet(self.biometric_key.encode("ascii"))
            digest = hashlib.sha256(self.biometric_key.encode("ascii")).hexdigest()
            if not re.fullmatch(r"[a-f0-9]{64}", self.biometric_key_sha256) or not hmac.compare_digest(digest, self.biometric_key_sha256):
                deny("BIOMETRIC_KEY_FINGERPRINT_MISMATCH")
        except StartupGuardError:
            raise
        except Exception:
            deny("INVALID_BIOMETRIC_KEY")

    def settings(self):
        # Explicit values; config.py's environment/defaults cannot select the DB.
        names = ("db_host", "db_port", "db_name", "db_user", "db_password", "biometric_key", "timezone", "session_hours", "challenge_seconds", "face_threshold", "demo_mode")
        return SimpleNamespace(**{name: getattr(self, name) for name in names})


def load_profile(path):
    try:
        target = Path(path).resolve(strict=True)
        if not target.is_relative_to((ROOT / ".work/recovery").resolve()) or target.suffix != ".json" or target.stat().st_size > 16384:
            deny("PRIVATE_RECOVERY_PROFILE_REQUIRED")
        def exact_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    deny("DUPLICATE_PROFILE_FIELD")
                result[key] = value
            return result
        data = json.loads(target.read_text(encoding="utf-8-sig"), object_pairs_hook=exact_object)
        if not isinstance(data, dict) or set(data) != {f.name for f in fields(ProductionProfile)}:
            deny("EXPLICIT_PROFILE_FIELDS_REQUIRED")
        return ProductionProfile(**data)
    except StartupGuardError:
        raise
    except Exception:
        deny("INVALID_PRIVATE_RECOVERY_PROFILE")


def required_grants():
    grants = {}
    def add(table, *privileges):
        grants.setdefault(table, set()).update((p, None) for p in privileges)
    for name in ("student_groups", "courses", "class_schedules", "class_sessions", "network_policies", "students"):
        add(name, "SELECT")
    for name in ("auth_sessions", "verification_attempts", "verification_challenges", "device_registration_challenges", "device_verification_challenges", "pending_device_registrations", "device_biometric_sessions", "device_activation_challenges", "attendance_device_challenges"):
        add(name, "SELECT", "INSERT", "UPDATE")
    for name in ("registered_devices", "attendance", "device_registration_events", "device_verification_events", "device_enrollment_events", "device_activation_events", "attendance_authorization_events"):
        add(name, "SELECT", "INSERT")
    for name in ("device_biometric_events", "network_verification_events"):
        add(name, "INSERT")
    grants["students"].update(("UPDATE", col) for col in ("face_encoding", "biometric_status", "consent_at", "updated_at"))
    grants["registered_devices"].update(("UPDATE", col) for col in ("status", "revoked_at", "revocation_reason"))
    return grants


def validate_grants(lines, profile):
    actual = {}
    usage = False
    for line in lines:
        # Never include SHOW GRANTS output in a diagnostic (it can contain hashes).
        match = re.fullmatch(r"GRANT (.+) ON (.+) TO `fyp_prod_runtime`@`127\.0\.0\.1`(?: IDENTIFIED BY PASSWORD '[^']*')?", line)
        if not match:
            deny("UNAPPROVED_RUNTIME_GRANTS")
        privileges, resource = match.groups()
        if privileges == "USAGE" and resource == "*.*":
            usage = True
            continue
        table = re.fullmatch(r"`" + re.escape(profile.db_name) + r"`\.`([a-z_]+)`", resource)
        if not table:
            deny("UNAPPROVED_RUNTIME_GRANTS")
        tokens = re.findall(r"(?:SELECT|INSERT|UPDATE)(?:\s*\([^()]+\))?", privileges)
        if ", ".join(tokens) != privileges:
            deny("UNAPPROVED_RUNTIME_GRANTS")
        for token in tokens:
            parts = re.fullmatch(r"(SELECT|INSERT|UPDATE)(?:\s*\(([^()]+)\))?", token)
            verb, columns = parts.groups()
            if columns is None:
                actual.setdefault(table[1], set()).add((verb, None))
            else:
                for col in columns.split(", "):
                    if not re.fullmatch(r"(?:`[a-z_]+`|[a-z_]+)", col):
                        deny("UNAPPROVED_RUNTIME_GRANTS")
                    actual.setdefault(table[1], set()).add((verb, col.strip("`")))
    if not usage or actual != required_grants():
        deny("RUNTIME_GRANT_SET_MISMATCH")


def validate_connection(raw, profile):
    cursor = None
    try:
        cursor = raw.cursor()
        cursor.execute("SELECT DATABASE(), CURRENT_USER(), @@port, @@datadir, @@basedir, VERSION(), @@read_only, @@bind_address, @@local_infile, @@event_scheduler, @@aria_recover_options, @@myisam_recover_options")
        schema, account, port, data, base, version, read_only, bind, infile, scheduler, aria, myisam = cursor.fetchone()
        if (schema, account, port, version, read_only, bind, infile) != (profile.db_name, RUNTIME + "@127.0.0.1", profile.db_port, profile.expected_version, 0, "127.0.0.1", 0):
            deny("DATABASE_IDENTITY_OR_SAFETY_MISMATCH")
        if path_identity(data) != path_identity(profile.expected_datadir) or path_identity(base) != path_identity(profile.expected_basedir):
            deny("DATABASE_DIRECTORY_MISMATCH")
        if str(scheduler).upper() not in ("OFF", "DISABLED") or str(aria).upper() != "OFF" or str(myisam).upper() != "OFF":
            deny("DATABASE_RECOVERY_OR_EVENT_POLICY_MISMATCH")
        cursor.execute("SHOW GRANTS")
        validate_grants([row[0] for row in cursor.fetchall()], profile)
    except StartupGuardError:
        raise
    except Exception:
        deny("DATABASE_GUARD_QUERY_FAILED")
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                deny("DATABASE_GUARD_CLOSE_FAILED")


def create_guarded_engine(profile):
    # No URL parameter or inherited DB environment override exists.
    target = URL.create("mysql+mysqlconnector", username=profile.db_user, password=profile.db_password, host=profile.db_host, port=profile.db_port, database=profile.db_name, query={"charset": "utf8mb4"})
    engine = create_engine(target, pool_pre_ping=True, connect_args={"connection_timeout": 3, "read_timeout": 5, "write_timeout": 5, "use_pure": True, "allow_local_infile": False}, hide_parameters=True).execution_options(isolation_level="READ COMMITTED")
    @event.listens_for(engine, "checkout")
    def check(raw, record, proxy):
        try:
            validate_connection(raw, profile)
        except Exception:
            record.invalidate()
            deny("DATABASE_CHECKOUT_REJECTED")
    return engine


def validate_startup(engine, profile):
    # Check URL before attempting any connection, including injected test engines.
    url = engine.url
    if (url.drivername, url.host, url.port, url.username, url.password, url.database, dict(url.query)) != ("mysql+mysqlconnector", profile.db_host, profile.db_port, profile.db_user, profile.db_password, profile.db_name, {"charset": "utf8mb4"}):
        deny("UNAPPROVED_ENGINE_TARGET")
    from sqlalchemy import text
    try:
        with engine.connect() as connection:
            # Runtime sees precisely its 24 granted tables. Offline admin checks all 26.
            rows = connection.execute(text("SELECT TABLE_NAME, ENGINE, TABLE_TYPE FROM information_schema.TABLES WHERE TABLE_SCHEMA=:schema"), {"schema": profile.db_name}).all()
            if {r[0] for r in rows} != set(required_grants()) or any(r[1:] != ("InnoDB", "BASE TABLE") for r in rows):
                deny("RUNTIME_SCHEMA_MISMATCH")
            from modules.biometrics.templates import decrypt_encoding
            for (cipher,) in connection.execute(text("SELECT face_encoding FROM students WHERE face_encoding IS NOT NULL AND face_encoding <> ''")):
                # Existing partner decryption only; no inference, enrollment or trust change.
                decrypt_encoding(cipher, profile.biometric_key)
    except StartupGuardError:
        raise
    except Exception:
        deny("DATABASE_STARTUP_VALIDATION_FAILED")
