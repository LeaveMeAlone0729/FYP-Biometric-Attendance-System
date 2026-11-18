"""Offline reset/restore rehearsal; never uses original credentials or database."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
import sys

import pytest
from sqlalchemy import Column, DateTime, ForeignKey, Integer, MetaData, String, Table, create_engine, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reset_demo_slot2 import ResetBlocked, reset_transaction, main, unpack


def fixture(*, foreign_owner=False, attendance_dependency=False):
    m = MetaData()
    students = Table('students', m, Column('student_id', String, primary_key=True), Column('face_encoding', String))
    devices = Table('registered_devices', m, Column('device_id', String, primary_key=True),
        Column('student_id', ForeignKey(students.c.student_id)), Column('slot_number', Integer),
        Column('status', String), Column('device_model', String), Column('public_key_fingerprint', String, unique=True),
        Column('registered_at', DateTime))
    Table('device_registration_events', m, Column('event_id', Integer, primary_key=True),
        Column('student_id', ForeignKey(students.c.student_id)), Column('device_id', String),
        Column('action', String), Column('outcome', String), Column('code', String), Column('occurred_at', DateTime))
    children = Table('proofs', m, Column('id', Integer, primary_key=True),
        Column('student_id', ForeignKey(students.c.student_id)), Column('device_id', ForeignKey(devices.c.device_id)))
    Table('proof_audits', m, Column('id', Integer, primary_key=True), Column('proof_id', ForeignKey(children.c.id)))
    Table('attendance', m, Column('id', Integer, primary_key=True), Column('student_id', String),
        *([Column('device_id', ForeignKey(devices.c.device_id))] if attendance_dependency else []))
    e = create_engine('sqlite://')
    m.create_all(e)
    with e.begin() as c:
        c.exec_driver_sql('PRAGMA foreign_keys=ON')
        c.execute(students.insert(), [{'student_id': 'DEMO001', 'face_encoding': 'UNCHANGED'},
                                    {'student_id': 'OTHER', 'face_encoding': 'OTHER_UNCHANGED'}])
        c.execute(devices.insert(), [dict(device_id='samsung', student_id='DEMO001', slot_number=1,
            status='ACTIVE', device_model='samsung SM-A346E', public_key_fingerprint='a'*64, registered_at=datetime(2026,11,1)),
            dict(device_id='local-demo-xiaomi', student_id='DEMO001', slot_number=2,
            status='ACTIVE', device_model='Xiaomi 2410CRP4CG', public_key_fingerprint='b'*64, registered_at=datetime(2026,11,9))])
        c.execute(children.insert(), dict(id=1, student_id='OTHER' if foreign_owner else 'DEMO001', device_id='local-demo-xiaomi'))
        c.execute(m.tables['proof_audits'].insert(), dict(id=1, proof_id=1))
        c.execute(m.tables['attendance'].insert(), dict(id=1, student_id='DEMO001',
            **({'device_id':'local-demo-xiaomi'} if attendance_dependency else {})))
    return e, m


def test_archive_reset_and_restore_rehearsal_preserves_samsung_accounts_attendance(tmp_path):
    e, m = fixture()
    with e.begin() as c:
        result = reset_transaction(c, tmp_path, 'b'*64, datetime(2026,11,18))
    assert result['slot1_preserved'] and result['attendance_preserved']
    raw = (tmp_path/'affected-records.json').read_bytes()
    manifest = json.loads((tmp_path/'manifest.json').read_text())
    assert hashlib.sha256(raw).hexdigest() == manifest['sha256']
    archive = unpack(raw)
    assert archive['rows']['registered_devices'][0]['device_id'] == 'local-demo-xiaomi'
    with e.connect() as c:
        assert c.execute(select(m.tables['registered_devices'].c.device_id)).scalars().all() == ['samsung']
        assert len(c.execute(select(m.tables['attendance'])).all()) == 1
        assert c.execute(select(m.tables['students'].c.face_encoding)).scalars().all() == ['UNCHANGED','OTHER_UNCHANGED']
        assert c.execute(select(m.tables['device_registration_events'].c.code)).scalar_one() == 'LOCAL_DEMO_SLOT2_RESET'
    # Prove archived rows restore under enabled FKs, inside an isolated transaction
    # that is rolled back. NEVER provide/run a live auto-restore operation.
    with e.connect() as c:
        transaction = c.begin()
        for table in m.sorted_tables:
            for row in archive['rows'].get(table.name, []):
                c.execute(table.insert(), row)
        assert len(c.execute(select(m.tables['registered_devices'])).all()) == 2
        assert len(c.execute(select(m.tables['proof_audits'])).all()) == 1
        transaction.rollback()
    e.dispose()


@pytest.mark.parametrize('option,code', [('foreign_owner','CROSS_STUDENT_REFERENCE'),
                                       ('attendance_dependency','PROTECTED_TABLE_DEPENDENCY')])
def test_cross_student_or_protected_dependency_stops_before_backup_or_delete(tmp_path, option, code):
    e,m = fixture(**{option:True})
    with pytest.raises(ResetBlocked, match=code):
        with e.begin() as c:
            reset_transaction(c,tmp_path,'b'*64,datetime(2026,11,18))
    assert not list(tmp_path.iterdir())
    with e.connect() as c:
        assert len(c.execute(select(m.tables['registered_devices'])).all()) == 2
    e.dispose()


def test_wrong_key_and_not_enabled_cannot_reset(tmp_path, monkeypatch, capsys):
    e,m = fixture()
    with pytest.raises(ResetBlocked,match='TARGET_NOT_APPROVED'):
        with e.begin() as c:
            reset_transaction(c,tmp_path,'c'*64,datetime(2026,11,18))
    monkeypatch.delenv('FYP_ENABLE_DEMO_SLOT2_RESET',raising=False)
    assert main(['--confirm','RESET-DEMO001-SLOT2','--fingerprint','b'*64,'--checkpoint',str(tmp_path/'new')]) == 1
    assert 'EXPLICIT_LOCAL_RESET_NOT_ENABLED' in capsys.readouterr().out
    with e.connect() as c:
        assert len(c.execute(select(m.tables['registered_devices'])).all()) == 2
    e.dispose()


def test_failure_after_backup_rolls_back_every_delete(tmp_path):
    e,m = fixture()
    # No audit table: exception after attempted deletes must roll back target/proofs.
    m.tables['device_registration_events'].drop(e)
    with pytest.raises(KeyError):
        with e.begin() as c:
            reset_transaction(c,tmp_path,'b'*64,datetime(2026,11,18))
    assert (tmp_path/'manifest.json').is_file()
    with e.connect() as c:
        assert len(c.execute(select(m.tables['registered_devices'])).all()) == 2
        assert len(c.execute(select(m.tables['proof_audits'])).all()) == 1
    e.dispose()
