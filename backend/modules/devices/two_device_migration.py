"""Resumable MariaDB Stage A migration. Verify new guards BEFORE releasing old uniqueness."""
import hashlib
import json
import re
import secrets
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

TABLE = "registered_devices"
SLOT_INDEX = "uq_registered_device_active_slot"
OWNER_INDEX = "ix_registered_devices_student_status"
EXPRESSION = "CASE WHEN status = 'ACTIVE' THEN slot_number ELSE NULL END"
CHECKS = {"ck_device_slot": "slot_number IN (1, 2)",
          "ck_device_status": "status IN ('ACTIVE', 'INACTIVE', 'REVOKED')"}


def require(condition, message="Stage A migration safety validation failed"):
    if not condition:
        raise RuntimeError(message)


def normalized(value):
    return re.sub(r"[\s`()]+", "", value).lower()


def indexes(connection, table=TABLE):
    return {i["name"]: i for i in inspect(connection).get_indexes(table)}


def legacy_indexes(connection, table=TABLE):
    return [name for name, index in indexes(connection, table).items()
            if index.get("unique") and index["column_names"] == ["student_id"]]


def verify_guards(connection):
    columns = {c["name"]: c for c in inspect(connection).get_columns(TABLE)}
    require(not columns['slot_number']['nullable'], 'slot_number must be NOT NULL')
    require(normalized(columns['slot_number'].get('default') or '') in ('1', "'1'"), 'Unexpected slot default')
    computed = columns["active_slot"].get("computed", {})
    require(computed.get('persisted') and normalized(computed.get('sqltext', '')) == normalized(EXPRESSION), 'Unexpected generated slot expression')
    constraints = {c["name"]: c["sqltext"] for c in inspect(connection).get_check_constraints(TABLE)}
    for name, expression in CHECKS.items():
        require(normalized(constraints.get(name, '')) == normalized(expression), 'Missing/wrong check: ' + name)
    actual = indexes(connection)
    require(actual[SLOT_INDEX]['unique'] and actual[SLOT_INDEX]['column_names'] == ['student_id', 'active_slot'], 'Stage A migration safety validation failed')
    require(actual[OWNER_INDEX]['column_names'] == ['student_id', 'status'], 'Stage A migration safety validation failed')
    require(any((i.get('unique') and i['column_names'] == ['public_key_fingerprint'] for i in actual.values())), 'Stage A migration safety validation failed')
    require(inspect(connection).get_pk_constraint(TABLE)['constrained_columns'] == ['device_id'], 'Stage A migration safety validation failed')
    require(connection.scalar(text('SELECT COUNT(*) FROM registered_devices WHERE slot_number NOT IN (1,2) OR slot_number IS NULL')) == 0, 'Stage A migration safety validation failed')
    require(connection.scalar(text("SELECT COUNT(*) FROM registered_devices WHERE status NOT IN ('ACTIVE','INACTIVE','REVOKED')")) == 0, 'Stage A migration safety validation failed')
    require(connection.scalar(text("SELECT COUNT(*) FROM registered_devices WHERE (status='ACTIVE' AND (active_slot IS NULL OR active_slot<>slot_number)) OR (status<>'ACTIVE' AND active_slot IS NOT NULL)")) == 0, 'Stage A migration safety validation failed')


def probe_constraints(connection):
    """Test an exact temporary schema clone; NEVER insert a probe into real records."""
    name = "stage_a_probe_" + secrets.token_hex(6)
    require(re.fullmatch('stage_a_probe_[0-9a-f]{12}', name), 'Stage A migration safety validation failed')
    connection.exec_driver_sql("CREATE TEMPORARY TABLE `" + name + "` LIKE registered_devices")
    try:
        # Remove student-only legacy guard ONLY from the temporary probe table.
        for old in legacy_indexes(connection, name):
            connection.exec_driver_sql("ALTER TABLE `"+name+"` DROP INDEX `"+old+"`")
        def insert(number, slot, status="ACTIVE"):
            connection.execute(text("INSERT INTO `"+name+"` (device_id,student_id,public_key_spki,public_key_fingerprint,device_name,device_model,platform,status,registered_at,slot_number) VALUES (:id,'PROBE','probe',:fingerprint,'Probe','Test','android',:status,'2000-01-01 00:00:00',:slot)"),
                dict(id="probe-"+str(number), fingerprint=format(number,"064x"),status=status,slot=slot))
        def reject(operation, errors):
            try:
                operation()
            except DBAPIError as exc:
                require(getattr(exc.orig, 'errno', None) in errors, str(exc.orig))
            else:
                raise RuntimeError("New device constraint failed its enforcement probe")
        insert(1, 1); insert(2, 2)
        reject(lambda: insert(3, 3), (4025,3819))
        reject(lambda: insert(4, 1), (1062,))
        reject(lambda: insert(5, None), (1048,))
        insert(6, 1, "REVOKED")
        reject(lambda: connection.exec_driver_sql("UPDATE `"+name+"` SET status='ACTIVE' WHERE device_id='probe-6'"), (1062,))
        reject(lambda: insert(7, 2, "UNKNOWN"), (4025,3819))
    finally:
        connection.exec_driver_sql("DROP TEMPORARY TABLE `"+name+"`")


def upgrade_two_device_schema(engine, release_legacy=False):
    if engine.dialect.name not in ("mysql", "mariadb"):
        raise RuntimeError("Controlled upgrade requires MariaDB/MySQL; use current models for fresh SQLite tests.")
    steps = []
    with engine.connect() as connection:
        database = connection.scalar(text("SELECT DATABASE()"))
        lock = "attendance.stage_a." + database
        require(connection.scalar(text('SELECT GET_LOCK(:name,10)'), dict(name=lock)) == 1, 'Migration already running')
        try:
            require(connection.scalar(text('SELECT @@check_constraint_checks')) == 1, 'CHECK enforcement is disabled')
            require(connection.scalar(text('SELECT @@unique_checks')) == 1, 'Unique enforcement is disabled')
            require(inspect(connection).has_table(TABLE), 'Apply Phase 1 first')
            references = connection.execute(text("SELECT TABLE_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME='registered_devices' AND REFERENCED_COLUMN_NAME='student_id'")).all()
            require(not references, 'A foreign key depends on the old student-only unique key; manual assessment required')
            def ddl(sql, description):
                connection.exec_driver_sql(sql); connection.commit(); steps.append(description)
            cols = {c["name"]:c for c in inspect(connection).get_columns(TABLE)}
            if "slot_number" not in cols:
                require(connection.scalar(text('SELECT COUNT(*) FROM (SELECT student_id FROM registered_devices GROUP BY student_id HAVING COUNT(*)>1) AS duplicates')) == 0, 'Cannot infer historical slots')
                ddl("ALTER TABLE registered_devices ADD COLUMN slot_number SMALLINT NULL", "add slot_number")
            require(connection.scalar(text('SELECT COUNT(*) FROM registered_devices WHERE slot_number IS NOT NULL AND slot_number NOT IN (1,2)')) == 0, 'Stage A migration safety validation failed')
            if connection.scalar(text("SELECT COUNT(*) FROM registered_devices WHERE slot_number IS NULL")):
                connection.exec_driver_sql("UPDATE registered_devices SET slot_number=1 WHERE slot_number IS NULL")
                connection.commit(); steps.append("backfill existing registrations into slot 1")
            slot = next(c for c in inspect(connection).get_columns(TABLE) if c["name"]=="slot_number")
            if slot["nullable"] or normalized(slot.get("default") or "") not in ("1","'1'"):
                ddl("ALTER TABLE registered_devices MODIFY COLUMN slot_number SMALLINT NOT NULL DEFAULT 1", "enforce slot default and non-null")
            cols = {c["name"]:c for c in inspect(connection).get_columns(TABLE)}
            if "active_slot" not in cols:
                ddl("ALTER TABLE registered_devices ADD COLUMN active_slot SMALLINT GENERATED ALWAYS AS ("+EXPRESSION+") STORED", "add generated ACTIVE slot")
            for name, definition in (("revoked_at","DATETIME NULL"),("revocation_reason","VARCHAR(255) NULL")):
                if name not in cols:
                    ddl("ALTER TABLE registered_devices ADD COLUMN "+name+" "+definition, "add "+name)
            present = {c["name"] for c in inspect(connection).get_check_constraints(TABLE)}
            for name, expression in CHECKS.items():
                if name not in present:
                    ddl("ALTER TABLE registered_devices ADD CONSTRAINT "+name+" CHECK ("+expression+")", "add "+name)
            actual = indexes(connection)
            if OWNER_INDEX not in actual:
                ddl("ALTER TABLE registered_devices ADD INDEX "+OWNER_INDEX+" (student_id,status)", "add owner/status FK-supporting index")
            if SLOT_INDEX not in actual:
                ddl("ALTER TABLE registered_devices ADD UNIQUE INDEX "+SLOT_INDEX+" (student_id,active_slot)", "add two-slot uniqueness")
            verify_guards(connection)
            probe_constraints(connection)
            connection.commit()
            # This is deliberately AFTER schema validation and actual enforcement probes.
            if release_legacy:
                for old in legacy_indexes(connection):
                    require(re.fullmatch('[A-Za-z0-9_]+', old), 'Stage A migration safety validation failed')
                    ddl("ALTER TABLE registered_devices DROP INDEX `"+old+"`", "release verified legacy unique index "+old)
            verify_guards(connection)
            if release_legacy:
                require(not legacy_indexes(connection), 'Stage A migration safety validation failed')
            connection.commit()
            return dict(database=database, steps=steps, guards_verified=True,
                        enforcement_probes_passed=True, legacy_unique_retained=bool(legacy_indexes(connection)))
        finally:
            connection.execute(text("SELECT RELEASE_LOCK(:name)"),dict(name=lock)); connection.commit()


def verify_original_data(engine, baseline):
    """Compare original-column projections, so added metadata never hides changed data."""
    with engine.connect() as connection:
        for table, expected in baseline.items():
            require(re.fullmatch('[A-Za-z0-9_]+', table), 'Stage A migration safety validation failed')
            columns = expected["columns"]
            require(all((re.fullmatch('[A-Za-z0-9_]+', column) for column in columns)), 'Stage A migration safety validation failed')
            rows = connection.exec_driver_sql("SELECT "+",".join("`"+c+"`" for c in columns)+" FROM `"+table+"`").mappings().all()
            encoded = sorted(json.dumps(dict(row),default=str,sort_keys=True,separators=(",",":")).encode() for row in rows)
            digest = hashlib.sha256()
            for row in encoded: digest.update(len(row).to_bytes(8,"big")); digest.update(row)
            require(len(rows) == expected['count'] and digest.hexdigest() == expected['sha256'], 'Original records changed: ' + table)
