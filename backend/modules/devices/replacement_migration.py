"""Controlled C1 metadata/check widening. No registration/data updates or index drops."""
from sqlalchemy import inspect,text
from .pending_models import PendingDeviceRegistration
from .biometric_models import DeviceBiometricSession
from .activation_models import DeviceActivationChallenge
from .pending_migration import verify_table,probe_pending_constraints
from .activation_migration import probe_activation_constraints
from .two_device_migration import require,verify_guards,normalized

TABLES=[PendingDeviceRegistration.__table__,DeviceBiometricSession.__table__,DeviceActivationChallenge.__table__]
OLD={"ck_pending_device_slot":"slot_number = 2", "ck_pending_device_operation":"operation = 'enroll_second_device'",
     "ck_pending_device_status":"status IN ('CHALLENGE_ISSUED','KEY_PROVEN','FAILED','EXPIRED','ACTIVATED')",
     "ck_device_bio_purpose":"operation = 'enroll_second_device' AND slot_number = 2",
     "ck_activation_purpose":"operation = 'enroll_second_device' AND slot_number = 2"}

def upgrade_replacement_schema(engine):
    require(engine.dialect.name=="mysql","C1 migration requires MariaDB/MySQL")
    with engine.connect() as c:
        lock="c1_migration_"+str(engine.url.database);steps=[]
        require(c.scalar(text("SELECT GET_LOCK(:name,10)"),dict(name=lock))==1,"C1 migration already running")
        try:
            require(c.scalar(text("SELECT @@check_constraint_checks"))==1,"CHECK enforcement disabled")
            require(c.scalar(text("SELECT @@unique_checks"))==1,"Unique enforcement disabled")
            verify_guards(c)
            for table in TABLES:require(inspect(c).has_table(table.name),"Apply existing B2/B3/B4 migrations first")
            cols={x['name'] for x in inspect(c).get_columns('pending_device_registrations')}
            if 'replaced_device_fingerprint' not in cols:
                c.exec_driver_sql('ALTER TABLE pending_device_registrations ADD COLUMN replaced_device_fingerprint VARCHAR(64) NULL');c.commit();steps.append('add replacement target fingerprint')
            for table in TABLES:
                for check in sorted((x for x in table.constraints if x.__class__.__name__=='CheckConstraint'),key=lambda x:x.name):
                    checks={x['name']:normalized(x['sqltext']) for x in inspect(c).get_check_constraints(table.name)}
                    expected=str(check.sqltext);actual=checks.get(check.name)
                    if actual==normalized(expected):continue
                    if actual is not None:
                        require(check.name in OLD and actual==normalized(OLD[check.name]),"Unexpected existing CHECK "+check.name)
                    else:require(check.name=='ck_pending_replacement_target',"Missing pre-existing CHECK "+check.name)
                    # A single atomic ALTER replaces a known legacy CHECK. ACTIVE-slot uniqueness is never released.
                    prefix=('DROP CONSTRAINT `'+check.name+'`, ') if actual is not None else ''
                    c.exec_driver_sql('ALTER TABLE `'+table.name+'` '+prefix+'ADD CONSTRAINT `'+check.name+'` CHECK ('+expected+')')
                    c.commit();steps.append('verify '+table.name+'.'+check.name)
                verify_table(c,table)
            probe_pending_constraints(c);probe_activation_constraints(c);verify_guards(c);c.commit()
            return dict(steps=steps,guards_verified=True,enforcement_probes_passed=True)
        finally:
            c.rollback();c.execute(text('SELECT RELEASE_LOCK(:name)'),dict(name=lock));c.commit()
