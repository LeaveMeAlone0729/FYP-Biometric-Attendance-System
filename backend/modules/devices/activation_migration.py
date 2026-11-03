"""Resumable additive B4 DDL. Application startup never runs this migration."""
import re
import secrets
from sqlalchemy import inspect,text
from sqlalchemy.exc import DBAPIError
from .activation_models import ACTIVATION_TABLES
from .pending_migration import verify_table
from .two_device_migration import require,verify_guards


def probe_activation_constraints(connection):
    name="b4_probe_"+secrets.token_hex(6)
    require(re.fullmatch("b4_probe_[0-9a-f]{12}",name),"Unsafe constraint probe")
    connection.exec_driver_sql("CREATE TEMPORARY TABLE `"+name+"` LIKE device_activation_challenges")
    try:
        def insert(identifier,slot=2,operation="enroll_second_device",result="PENDING",consumed=None,pending="pending"):
            connection.execute(text("INSERT INTO `"+name+"` (challenge_id,student_id,auth_token_hash,pending_registration_id,candidate_device_id,public_key_fingerprint,approval_id,trusted_template_revision_id,operation,slot_number,signing_payload,created_at,expires_at,result,consumed_at) VALUES (:id,'student','auth',:pending,'candidate','fingerprint','approval','revision',:operation,:slot,'payload','2000-01-01','2000-01-02',:result,:consumed)"),dict(id=identifier,slot=slot,operation=operation,result=result,consumed=consumed,pending=pending))
        insert("first")
        for i,values in enumerate((dict(),dict(slot=3),dict(operation="attendance"),dict(result="PASS"),dict(result="TRUSTED")),1):
            try:insert(str(i),pending="pending" if not values else "invalid"+str(i),**values)
            except DBAPIError as exc:require(getattr(exc.orig,"errno",None) in (1062,4025),"Unexpected B4 constraint error")
            else:raise RuntimeError("Activation constraint did not reject invalid row")
        connection.exec_driver_sql("UPDATE `"+name+"` SET result='FAIL',consumed_at='2000-01-01'")
        insert("new")
    finally:connection.exec_driver_sql("DROP TEMPORARY TABLE IF EXISTS `"+name+"`")


def upgrade_activation_schema(engine):
    require(engine.dialect.name=="mysql","B4 DDL validation requires MariaDB/MySQL")
    with engine.connect() as connection:
        lock="b4_migration_"+str(engine.url.database)
        require(connection.scalar(text("SELECT GET_LOCK(:name,10)"),dict(name=lock))==1,"B4 migration already running")
        created=[]
        try:
            require(connection.scalar(text("SELECT @@check_constraint_checks"))==1,"CHECK enforcement disabled")
            require(connection.scalar(text("SELECT @@unique_checks"))==1,"Unique enforcement disabled")
            verify_guards(connection)
            require(inspect(connection).has_table("pending_device_registrations"),"Apply B2 first")
            for table in ACTIVATION_TABLES:
                if inspect(connection).has_table(table.name):verify_table(connection,table)
            for table in ACTIVATION_TABLES:
                if not inspect(connection).has_table(table.name):table.create(connection);created.append(table.name)
                verify_table(connection,table);connection.commit()
            probe_activation_constraints(connection)
            return dict(created_tables=created,guards_verified=True,enforcement_probes_passed=True)
        finally:
            connection.rollback();connection.execute(text("SELECT RELEASE_LOCK(:name)"),dict(name=lock));connection.commit()
