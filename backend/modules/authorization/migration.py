from database_compat import verify_check_enforcement
"""Add only attendance-specific nonce/audit tables; no existing data updates."""
import secrets
from sqlalchemy import inspect,text
from sqlalchemy.exc import DBAPIError
from modules.devices.pending_migration import verify_table
from modules.devices.two_device_migration import require
from .models import AUTHORIZATION_TABLES

def upgrade_attendance_authorization_schema(engine):
    require(engine.dialect.name=='mysql','Attendance authorization migration requires MariaDB/MySQL')
    with engine.connect() as c:
        lock='p5_migration_'+str(engine.url.database);created=[]
        require(c.scalar(text('SELECT GET_LOCK(:name,10)'),dict(name=lock))==1,'Another attendance migration is running')
        try:
            verify_check_enforcement(c)
            require(c.scalar(text('SELECT @@unique_checks'))==1,'Unique enforcement disabled')
            for name in ['students','auth_sessions','verification_challenges','registered_devices','network_verification_events']:
                require(inspect(c).has_table(name),'Missing prerequisite '+name)
            for table in AUTHORIZATION_TABLES:
                if inspect(c).has_table(table.name):verify_table(c,table)
            for table in AUTHORIZATION_TABLES:
                if not inspect(c).has_table(table.name):table.create(c);c.commit();created.append(table.name)
                verify_table(c,table)
            for name in ['attendance','verification_attempts','verification_challenges','students','auth_sessions','registered_devices','class_sessions','class_schedules','network_policies','network_verification_events',*[t.name for t in AUTHORIZATION_TABLES]]:
                require(inspect(c).get_table_options(name).get('mysql_engine','').lower()=='innodb','Transactional InnoDB storage required: '+name)
            name='p5_probe_'+secrets.token_hex(6)
            c.exec_driver_sql('CREATE TEMPORARY TABLE `'+name+'` LIKE attendance_device_challenges')
            try:
                sql="INSERT INTO `"+name+"` (challenge_id,student_id,auth_token_hash,attendance_challenge_id,session_id,device_id,key_fingerprint,operation,signing_payload,created_at,expires_at,result) VALUES (:id,'probe','probe',:attempt,1,'probe','probe',:operation,'probe','2000-01-01','2000-01-02',:result)"
                values=dict(id='first',attempt='attempt',operation='attendance_authorization',result='PENDING');c.execute(text(sql),values)
                for i,changes in enumerate([{},dict(operation='device_status',attempt='other'),dict(result='PASS',attempt='other'),dict(result='UNKNOWN',attempt='other')]):
                    try:c.execute(text(sql),{**values,'id':'invalid'+str(i),**changes})
                    except DBAPIError as exc:require(getattr(exc.orig,'errno',None) in (1062,4025,3819),'Unexpected nonce guard error')
                    else:raise RuntimeError('Attendance nonce guard failed')
                c.exec_driver_sql("UPDATE `"+name+"` SET result='FAIL',consumed_at='2000-01-01'")
                c.execute(text(sql),{**values,'id':'renewed'})
            finally:c.exec_driver_sql('DROP TEMPORARY TABLE `'+name+'`')
            c.commit();return dict(created_tables=created,guards_verified=True,enforcement_probes_passed=True)
        finally:c.rollback();c.execute(text('SELECT RELEASE_LOCK(:name)'),dict(name=lock));c.commit()
