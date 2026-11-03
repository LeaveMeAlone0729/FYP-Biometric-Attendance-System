"""Evidence-gated replacement migration; preserve every existing row."""
import argparse
import hashlib
import json
import re
import socket
from dataclasses import replace
from pathlib import Path
from config import Settings
from database import make_engine
from modules.devices.replacement_migration import upgrade_replacement_schema
from modules.devices.two_device_migration import require,verify_original_data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence",type=Path,required=True)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-restored-copy",action="store_true")
    mode.add_argument("--apply-production",action="store_true")
    args=parser.parse_args()
    evidence=json.loads(args.evidence.read_text(encoding="utf-8"))
    folder=Path(evidence["backup_path"])
    require(evidence.get("restored_backup_verified"),"Verify backup restoration first")
    require(hashlib.sha256((folder/'database.sql').read_bytes()).hexdigest()==evidence['sql_sha256'],"SQL backup hash mismatch")
    for config in (folder/'backend.env',Path(__file__).parent/'.env'):
        require(hashlib.sha256(config.read_bytes()).hexdigest()==evidence['configuration_sha256'],"Matching configuration required")
    settings=Settings();target=settings.db_name if args.apply_production else evidence['restored_database']
    require(settings.db_name==evidence['source_database'],"Wrong source database")
    if args.apply_production:
        require(evidence.get('c1_restored_migration_verified'),"Validate this backup's restored copy first")
        try: sock=socket.create_connection(('127.0.0.1',8000),1)
        except OSError: pass
        else:
            sock.close();raise RuntimeError('Stop all old backend workers before production migration')
    else:
        require(target!=settings.db_name and re.fullmatch('attendance_c1_restore_[0-9a-f]{12}',target),"Not an isolated C1 restored copy")
    engine=make_engine(replace(settings,db_name=target))
    try:
        verify_original_data(engine,evidence['baseline'])
        report=upgrade_replacement_schema(engine)
        verify_original_data(engine,evidence['baseline'])
        rerun=upgrade_replacement_schema(engine)
        require(not rerun['steps'],'C1 migration rerun must be a no-op')
        verify_original_data(engine,evidence['baseline'])
        mode_name='production' if args.apply_production else 'restored'
        evidence['c1_'+mode_name+'_migration_verified']=True
        evidence['c1_'+mode_name+'_migration_report']={**report,'idempotent_rerun':rerun,'all_original_records_preserved':True}
        args.evidence.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(evidence['c1_'+mode_name+'_migration_report']))
    finally:engine.dispose()


if __name__=='__main__':main()
