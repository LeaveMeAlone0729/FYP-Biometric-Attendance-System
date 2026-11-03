"""Additive B3 untrusted-session migration. Existing records are untouched."""
import re
import secrets
from sqlalchemy import inspect,text
from sqlalchemy.exc import DBAPIError
from .biometric_models import BIOMETRIC_TABLES
from .pending_migration import verify_table
from .two_device_migration import require,verify_guards


def probe_biometric_constraints(connection):
    name="b3_probe_"+secrets.token_hex(6)
    require(re.fullmatch("b3_probe_[0-9a-f]{12}",name),"Unsafe probe name")
    connection.exec_driver_sql("CREATE TEMPORARY TABLE `"+name+"` LIKE device_biometric_sessions")
    try:
        def insert(number,stage="FACE",slot=2,fingers=None,valid=0):
            connection.execute(text("INSERT INTO `"+name+"` (approval_id,pending_registration_id,student_id,auth_token_hash,candidate_device_id,public_key_fingerprint,slot_number,operation,template_binding,stage,fingers,valid_frames,frame_count,frame_hashes,created_at,expires_at) VALUES (:id,'pending','student','auth','candidate','fingerprint',:slot,'enroll_second_device','binding',:stage,:fingers,:valid,0,'[]','2000-01-01','2000-01-02')"),dict(id=str(number),stage=stage,slot=slot,fingers=fingers,valid=valid))
        insert(1)
        for number,values in enumerate((dict(),dict(stage="TRUSTED"),dict(slot=3),dict(fingers=6),dict(valid=4)),2):
            try:insert(number,**values)
            except DBAPIError as exc:require(getattr(exc.orig,"errno",None) in (1062,4025),"Unexpected B3 constraint error")
            else:raise RuntimeError("B3 constraint did not reject invalid session")
        connection.exec_driver_sql("UPDATE `"+name+"` SET stage='COMPLETED_UNTRUSTED'")
        insert(9)
    finally:connection.exec_driver_sql("DROP TEMPORARY TABLE IF EXISTS `"+name+"`")


def upgrade_biometric_schema(engine):
    require(engine.dialect.name=="mysql","B3 migration requires MariaDB/MySQL")
    with engine.connect() as connection:
        lock="b3_migration_"+str(engine.url.database)
        require(connection.scalar(text("SELECT GET_LOCK(:name,10)"),dict(name=lock))==1,"B3 migration already running")
        created=[]
        try:
            require(connection.scalar(text("SELECT @@check_constraint_checks"))==1,"CHECK enforcement disabled")
            require(connection.scalar(text("SELECT @@unique_checks"))==1,"Unique enforcement disabled")
            verify_guards(connection)
            require(inspect(connection).has_table("pending_device_registrations"),"Apply B2 first")
            for table in BIOMETRIC_TABLES:
                if inspect(connection).has_table(table.name):verify_table(connection,table)
            for table in BIOMETRIC_TABLES:
                if not inspect(connection).has_table(table.name):table.create(connection);created.append(table.name)
                verify_table(connection,table);connection.commit()
            probe_biometric_constraints(connection)
            return dict(created_tables=created,guards_verified=True,enforcement_probes_passed=True)
        finally:
            connection.rollback();connection.execute(text("SELECT RELEASE_LOCK(:name)"),dict(name=lock));connection.commit()
