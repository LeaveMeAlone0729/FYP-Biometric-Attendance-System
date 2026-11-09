"""Offline operator validation only; no production migration or trust seeding."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from modules.devices.management_migration import upgrade_management_schema
from modules.devices.two_device_migration import require, verify_original_data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--evidence', required=True, type=Path)
    args = parser.parse_args()
    engine = None
    try:
        p = json.loads(args.profile.read_text())
        e = json.loads(args.evidence.read_text())
        require(set(p) == {'db_host','db_port','db_name','db_user','db_password','expected_datadir'}, 'Exact private profile required')
        require(p['db_host'] == '127.0.0.1' and type(p['db_port']) is int
            and 1024 <= p['db_port'] <= 65535 and p['db_port'] != 3306
            and p['db_user'] == 'fyp_device_migrator' and len(p['db_password']) >= 24
            and re.fullmatch(r'fypdevicemgmt_restore_[0-9a-f]{12}', p['db_name']), 'Not a disposable profile')
        datadir = Path(p['expected_datadir']).resolve()
        require(datadir.is_relative_to(Path('C:/FYP/DB-DeviceManagement').resolve()), 'Dedicated disposable data directory required')
        require(e.get('restored_backup_verified') is True and e['restored_database'] == p['db_name']
            and e['source_database'] != p['db_name'], 'Verified isolated restore evidence required')
        require(hashlib.sha256(Path(e['sql_dump']).read_bytes()).hexdigest() == e['sql_sha256'], 'Backup hash mismatch')
        url = URL.create('mysql+mysqlconnector', host=p['db_host'], port=p['db_port'],
            database=p['db_name'], username=p['db_user'], password=p['db_password'])
        engine = create_engine(url, hide_parameters=True, connect_args={
            'connection_timeout':3,'read_timeout':5,'write_timeout':5,'use_pure':True})
        with engine.connect() as c:
            port, schema, directory = c.execute(text('SELECT @@port,DATABASE(),@@datadir')).one()
            require((port,schema) == (p['db_port'],p['db_name']) and Path(directory).resolve() == datadir,
                    'Wrong disposable server')
        verify_original_data(engine, e['baseline'])
        report = upgrade_management_schema(engine)
        verify_original_data(engine, e['baseline'])
        require(not upgrade_management_schema(engine)['created_tables'], 'Resume must be a no-op')
        print(json.dumps(dict(result='PASS', **report)))
        return 0
    except Exception:
        print('DEVICE_MANAGEMENT_MIGRATION_REJECTED; inspect private isolated profile/evidence')
        return 1
    finally:
        if engine is not None: engine.dispose()


if __name__ == '__main__': raise SystemExit(main())
