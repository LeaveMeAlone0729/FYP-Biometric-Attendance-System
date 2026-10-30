"""Evidence-gated Stage A migration. Never drops old uniqueness without verified guards."""
import argparse
import hashlib
import json
import socket
from dataclasses import replace
from pathlib import Path
from config import Settings
from database import make_engine
from modules.devices.two_device_migration import upgrade_two_device_schema, verify_original_data, require


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence",type=Path,required=True,help="Private verified backup manifest")
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-restored-copy",action="store_true")
    mode.add_argument("--apply-production",action="store_true")
    args=parser.parse_args()
    evidence=json.loads(args.evidence.read_text(encoding="utf-8"))
    folder=Path(evidence["backup_path"])
    require(hashlib.sha256((folder / 'database.sql').read_bytes()).hexdigest() == evidence['sql_sha256'], 'Backup hash mismatch')
    require(hashlib.sha256((folder / 'backend.env').read_bytes()).hexdigest() == evidence['configuration_sha256'], 'Backup configuration mismatch')
    require(hashlib.sha256((Path(__file__).parent / '.env').read_bytes()).hexdigest() == evidence['configuration_sha256'], 'Current configuration differs from backup')
    settings=Settings()
    require(settings.db_name == evidence['source_database'], 'Stage A migration safety validation failed')
    if args.apply_production:
        require(evidence.get('restored_migration_verified'), 'Restored-copy migration validation is required first')
        try:
            connection=socket.create_connection(("127.0.0.1",8000),timeout=1)
        except OSError:
            pass
        else:
            connection.close(); raise RuntimeError("Stop the old backend workers on port 8000 first")
    target=evidence["restored_database"] if args.validate_restored_copy else settings.db_name
    require(target != settings.db_name if args.validate_restored_copy else target == settings.db_name, 'Stage A migration safety validation failed')
    engine=make_engine(replace(settings,db_name=target))
    try:
        verify_original_data(engine,evidence["baseline"])
        prepared=upgrade_two_device_schema(engine,release_legacy=False)
        verify_original_data(engine,evidence["baseline"])
        finished=upgrade_two_device_schema(engine,release_legacy=True)
        verify_original_data(engine,evidence["baseline"])
        rerun=upgrade_two_device_schema(engine,release_legacy=True)
        require(rerun['steps'] == [], 'Rerun must be a no-op')
        report=dict(prepared=prepared,finished=finished,idempotent_rerun=rerun,all_original_records_preserved=True)
        if args.validate_restored_copy:
            evidence["restored_migration_verified"]=True
            evidence["restored_migration_report"]=report
        else:
            evidence["production_migration_verified"]=True
            evidence["production_migration_report"]=report
        args.evidence.write_text(json.dumps(evidence,indent=2),encoding="utf-8")
        print(json.dumps(report,indent=2))
    finally:
        engine.dispose()

if __name__=="__main__":
    main()
