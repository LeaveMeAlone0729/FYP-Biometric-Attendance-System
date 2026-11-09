from sqlalchemy import inspect
from .models import BleBase


def upgrade(engine):
    for table in BleBase.metadata.sorted_tables:
        table.create(engine,checkfirst=True)
        i=inspect(engine)
        if {c['name'] for c in i.get_columns(table.name)}!=set(table.c.keys()):raise ValueError('BLE_SCHEMA_DRIFT')
        if set(i.get_pk_constraint(table.name)['constrained_columns'])!={c.name for c in table.primary_key}:raise ValueError('BLE_PRIMARY_KEY_MISMATCH')
        for fk in table.foreign_keys:
            if not any(fk.parent.name in r['constrained_columns'] and r['referred_table']==fk.column.table.name and fk.column.name in r['referred_columns'] for r in i.get_foreign_keys(table.name)):raise ValueError('BLE_FOREIGN_KEY_MISMATCH')
    if not any(set(r['column_names'])=={'student_id','device_id','evidence_hash'} for r in inspect(engine).get_unique_constraints('classroom_ble_challenges')):raise ValueError('BLE_REPLAY_CONSTRAINT_MISSING')
    return list(BleBase.metadata.tables)
