from database_compat import verify_check_enforcement
"""Add three empty FR-06 tables; reject drift and never alter existing records."""
import secrets
from sqlalchemy import inspect,text,MetaData,Integer
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.exc import DBAPIError
from modules.devices.pending_migration import verify_table
from modules.devices.two_device_migration import require,normalized
from .models import NETWORK_TABLES

def verify_network_table(c,table):
    # MariaDB reflects SQLAlchemy Boolean as TINYINT(1), not Boolean affinity.
    if table.name=='network_policies':
        actual=next(col for col in inspect(c).get_columns(table.name) if col['name']=='enabled')
        require(isinstance(actual['type'],TINYINT) and actual['type'].display_width==1,'Wrong policy boolean storage')
        expected=table.to_metadata(MetaData());expected.c.enabled.type=Integer()
        verify_table(c,expected)
    else:verify_table(c,table)

def probe_network_constraints(c):
    name='p4_probe_'+secrets.token_hex(6)
    c.exec_driver_sql('CREATE TEMPORARY TABLE `'+name+'` LIKE network_policies')
    try:
        c.exec_driver_sql("INSERT INTO `"+name+"` (network_id,network_name,network_cidr,created_at,updated_at) VALUES ('probe','probe','192.0.2.0/24','2000-01-01','2000-01-01')")
        require(c.exec_driver_sql('SELECT enabled FROM `'+name+'`').scalar()==0,'Policies must default to disabled')
        try:c.exec_driver_sql('UPDATE `'+name+'` SET enabled=2')
        except DBAPIError as exc:require(getattr(exc.orig,'errno',None) in (4025,3819),'Unexpected policy probe error')
        else:raise RuntimeError('Invalid enabled status accepted')
    finally:c.exec_driver_sql('DROP TEMPORARY TABLE `'+name+'`')
    c.exec_driver_sql('CREATE TEMPORARY TABLE `'+name+'` LIKE network_verification_events')
    try:
        sql="INSERT INTO `"+name+"` (student_id,auth_token_hash,operation,source_ip,result,reason_code,verified_at) VALUES ('probe','probe',:operation,'192.0.2.1',:result,'probe','2000-01-01')"
        c.execute(text(sql),dict(operation='network_diagnostic',result='FAIL'))
        for values in (dict(operation='network_diagnostic',result='PASS'),dict(operation='attendance_authorization',result='FAIL'),dict(operation='network_diagnostic',result='BAD')):
            try:c.execute(text(sql),values)
            except DBAPIError as exc:require(getattr(exc.orig,'errno',None) in (4025,3819),'Unexpected audit probe error')
            else:raise RuntimeError('Invalid network audit accepted')
    finally:c.exec_driver_sql('DROP TEMPORARY TABLE `'+name+'`')

def upgrade_network_schema(engine):
    require(engine.dialect.name=='mysql','Network migration requires MariaDB/MySQL')
    with engine.connect() as c:
        lock='p4_migration_'+str(engine.url.database);created=[]
        require(c.scalar(text('SELECT GET_LOCK(:name,10)'),dict(name=lock))==1,'Another network migration is running')
        try:
            verify_check_enforcement(c)
            require(c.scalar(text('SELECT @@unique_checks'))==1,'Unique enforcement disabled')
            for table in NETWORK_TABLES:
                if inspect(c).has_table(table.name):verify_network_table(c,table)
            for table in NETWORK_TABLES:
                if not inspect(c).has_table(table.name):table.create(c);created.append(table.name);c.commit()
                verify_network_table(c,table)
            indexes={i['name']:i['column_names'] for i in inspect(c).get_indexes('network_verification_events')}
            require(indexes.get('ix_network_event_student_time')==['student_id','verified_at'],'Missing student/time audit index')
            default=next(col for col in inspect(c).get_columns('network_policies') if col['name']=='enabled')['default']
            require(normalized(str(default)) in ('0',"'0'"),'Policy default must be disabled')
            probe_network_constraints(c);c.commit()
            return dict(created_tables=created,guards_verified=True,enforcement_probes_passed=True,policies_seeded=False)
        finally:
            c.rollback();c.execute(text('SELECT RELEASE_LOCK(:name)'),dict(name=lock));c.commit()
