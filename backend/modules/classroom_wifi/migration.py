"""Resumable additive optional schema; operator must back up and rehearse first."""
from sqlalchemy import inspect
from .models import ClassroomBase


def upgrade(engine):
    inspector = inspect(engine)
    for table in ClassroomBase.metadata.sorted_tables:
        if not inspector.has_table(table.name): table.create(engine, checkfirst=True)
        inspector = inspect(engine)
        columns = {c['name']: c for c in inspector.get_columns(table.name)}
        if set(columns) != set(table.c.keys()): raise ValueError('CLASSROOM_SCHEMA_DRIFT_' + table.name)
        if set(inspector.get_pk_constraint(table.name)['constrained_columns']) != {c.name for c in table.primary_key}:
            raise ValueError('CLASSROOM_PRIMARY_KEY_MISMATCH')
        for fk in table.foreign_keys:
            if not any(fk.parent.name in row['constrained_columns'] and row['referred_table'] == fk.column.table.name
                       and fk.column.name in row['referred_columns'] for row in inspector.get_foreign_keys(table.name)):
                raise ValueError('CLASSROOM_FOREIGN_KEY_MISMATCH')
    unique = inspect(engine).get_unique_constraints('classroom_wifi_challenges')
    if not any(set(row['column_names']) == {'student_id', 'device_id', 'evidence_hash'} for row in unique):
        raise ValueError('CLASSROOM_REPLAY_CONSTRAINT_MISSING')
    return list(ClassroomBase.metadata.tables)
