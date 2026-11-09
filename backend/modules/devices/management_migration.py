from database_compat import verify_check_enforcement
"""Resumable additive DDL; only an explicitly named isolated restored DB."""
import re
from sqlalchemy import inspect, text
from .management_models import MANAGEMENT_TABLES
from .pending_migration import verify_table
from .two_device_migration import require, verify_guards


def upgrade_management_schema(engine):
    url = engine.url
    require(engine.dialect.name == 'mysql' and url.host == '127.0.0.1'
        and url.port is not None and url.port != 3306
        and re.fullmatch(r'(?:fypdevicemgmt_restore_|fypmysqltest_|fypmysqlcase_)[0-9a-f]{12}', url.database or ''),
        'Only an explicit isolated restored MariaDB is accepted; no production mode')
    created = []
    with engine.connect() as connection:
        lock = 'device_management_' + url.database
        require(connection.scalar(text('SELECT GET_LOCK(:name,10)'), {'name': lock}) == 1,
                'Another device-management migration is running')
        try:
            verify_check_enforcement(connection)
            require(connection.scalar(text('SELECT @@unique_checks')) == 1, 'Unique checks disabled')
            verify_guards(connection)
            require(inspect(connection).has_table('device_biometric_sessions'), 'Apply existing B3 schema first')
            # Validate all existing objects before any new DDL; never rewrite them.
            for table in MANAGEMENT_TABLES:
                if inspect(connection).has_table(table.name): verify_table(connection, table)
            for table in MANAGEMENT_TABLES:
                if not inspect(connection).has_table(table.name):
                    table.create(connection); created.append(table.name)
                verify_table(connection, table)
                connection.commit()
            return dict(created_tables=created, original_records_updated=False)
        finally:
            connection.rollback()
            connection.execute(text('SELECT RELEASE_LOCK(:name)'), {'name': lock})
            connection.commit()
