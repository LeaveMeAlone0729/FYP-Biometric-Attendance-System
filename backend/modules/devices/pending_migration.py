"""Add only B2 tables; validate every resumed step and preserve Stage A guards."""
import re
import secrets
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError
from .pending_models import PENDING_TABLES
from .two_device_migration import require, normalized, verify_guards


def verify_table(connection, table):
    inspector = inspect(connection)
    actual = {c["name"]: c for c in inspector.get_columns(table.name)}
    require(set(actual) == set(table.columns.keys()), "Unexpected columns: " + table.name)
    for column in table.columns:
        found = actual[column.name]
        require(found["nullable"] == column.nullable, "Wrong nullability: " + column.name)
        require(found["type"]._type_affinity is column.type._type_affinity, "Wrong type: " + column.name)
        require(getattr(found["type"], "length", None) == getattr(column.type, "length", None), "Wrong length: " + column.name)
        if column.computed:
            require(found.get("computed", {}).get("persisted") and normalized(found["computed"]["sqltext"]) == normalized(str(column.computed.sqltext)), "Wrong generated pending slot")
    require(inspector.get_pk_constraint(table.name)["constrained_columns"] == [c.name for c in table.primary_key], "Wrong primary key")
    checks = {c["name"]: normalized(c["sqltext"]) for c in inspector.get_check_constraints(table.name)}
    for constraint in table.constraints:
        if constraint.__class__.__name__ == "CheckConstraint":
            require(checks.get(constraint.name) == normalized(str(constraint.sqltext)), "Missing/wrong CHECK: " + constraint.name)
    uniques = {tuple(i["column_names"]) for i in inspector.get_indexes(table.name) if i.get("unique")}
    for constraint in table.constraints:
        if constraint.__class__.__name__ == "UniqueConstraint":
            require(tuple(c.name for c in constraint.columns) in uniques, "Missing unique pending guard")
    fks = {(tuple(f["constrained_columns"]), f["referred_table"], tuple(f["referred_columns"])) for f in inspector.get_foreign_keys(table.name)}
    for fk in table.foreign_keys:
        require(((fk.parent.name,), fk.column.table.name, (fk.column.name,)) in fks, "Missing pending foreign key")


def probe_pending_constraints(connection):
    name = "b2_probe_" + secrets.token_hex(6)
    require(re.fullmatch("b2_probe_[0-9a-f]{12}", name), "Unsafe probe name")
    connection.exec_driver_sql("CREATE TEMPORARY TABLE `" + name + "` LIKE pending_device_registrations")
    try:
        def insert(number, slot=2, status="CHALLENGE_ISSUED", operation="enroll_second_device"):
            connection.execute(text("INSERT INTO `"+name+"` (pending_registration_id,candidate_device_id,student_id,auth_token_hash,slot_one_device_id,slot_number,operation,public_key_spki,public_key_fingerprint,device_name,device_model,signing_payload,status,created_at,expires_at,challenge_expires_at) VALUES (:id,:id,'PROBE','probe','probe',:slot,:operation,'probe','probe','probe','probe','probe',:status,'2000-01-01','2000-01-02','2000-01-02')"),dict(id="probe"+str(number),slot=slot,status=status,operation=operation))
        insert(1)
        for number,values in enumerate((dict(),dict(slot=3),dict(status="ACTIVE"),dict(status="FAILED",operation="attendance")),2):
            try: insert(number,**values)
            except DBAPIError as exc:
                require(getattr(exc.orig,"errno",None) in (1062,4025), "Unexpected constraint probe error")
            else: raise RuntimeError("Pending constraint did not reject invalid row")
        connection.exec_driver_sql("UPDATE `"+name+"` SET status='EXPIRED'")
        insert(9)
    finally:
        connection.exec_driver_sql("DROP TEMPORARY TABLE IF EXISTS `"+name+"`")


def upgrade_pending_schema(engine):
    if engine.dialect.name != "mysql":
        raise RuntimeError("B2 production migration requires MariaDB/MySQL")
    with engine.connect() as connection:
        lock="b2_migration_"+str(connection.engine.url.database)
        require(connection.scalar(text("SELECT GET_LOCK(:name,10)"),dict(name=lock)) == 1, "Another B2 migration is running")
        created=[]
        try:
            require(connection.scalar(text("SELECT @@check_constraint_checks")) == 1, "CHECK enforcement disabled")
            require(connection.scalar(text("SELECT @@unique_checks")) == 1, "Unique enforcement disabled")
            verify_guards(connection)
            # Existing malformed tables fail closed; never replace/drop them.
            for table in PENDING_TABLES:
                if inspect(connection).has_table(table.name): verify_table(connection, table)
            for table in PENDING_TABLES:
                if not inspect(connection).has_table(table.name):
                    table.create(connection)
                    created.append(table.name)
                verify_table(connection, table)
                connection.commit()
            probe_pending_constraints(connection)
            verify_guards(connection)
            connection.commit()
            return dict(created_tables=created, guards_verified=True, enforcement_probes_passed=True)
        finally:
            connection.rollback()
            connection.execute(text("SELECT RELEASE_LOCK(:name)"),dict(name=lock)); connection.commit()
