"""Upgrade existing demo databases without resetting accounts or biometric data."""
from sqlalchemy import inspect, text


def upgrade_schema(engine):
    """Remove retired installation-binding columns; safe to run repeatedly.

    Removing the old NOT NULL auth column is necessary before the simplified
    login can insert sessions into an existing database. Fresh databases already
    use the current models and require no changes.
    """
    removed = []
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table in ('students', 'auth_sessions'):
            if not inspector.has_table(table):
                continue
            if 'device_hash' in {column['name'] for column in inspector.get_columns(table)}:
                # Both table names are fixed constants, never user input.
                connection.execute(text(f'ALTER TABLE `{table}` DROP COLUMN device_hash'))
                removed.append(f'{table}.device_hash')
    return removed


if __name__ == '__main__':
    from config import Settings
    from database import make_engine

    engine = make_engine(Settings())
    try:
        removed = upgrade_schema(engine)
        print('Schema updated: ' + ', '.join(removed) if removed else 'Schema is already current.')
    finally:
        engine.dispose()
