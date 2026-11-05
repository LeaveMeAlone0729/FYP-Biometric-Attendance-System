"""Trusted local operator CLI, not a student HTTP API. No default campus ranges."""
import argparse,getpass,json
from sqlalchemy import select
from config import Settings,local_now
from database import make_engine,make_sessions
from modules.networks.models import NetworkPolicy
from modules.networks.policies import put_policy

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('list')
    put=commands.add_parser('put');put.add_argument('--id',required=True);put.add_argument('--name',required=True);put.add_argument('--cidr',required=True)
    put.add_argument('--enable',action='store_true',help='Explicitly enable this policy; omitted means disabled')
    for action in ('enable','disable'):
        sub=commands.add_parser(action);sub.add_argument('--id',required=True)
    args=parser.parse_args();settings=Settings();engine=make_engine(settings)
    try:
        with make_sessions(engine).begin() as db:
            if args.command=='list':
                print(json.dumps([dict(network_id=p.network_id,network_name=p.network_name,network_cidr=p.network_cidr,enabled=p.enabled) for p in db.scalars(select(NetworkPolicy).order_by(NetworkPolicy.network_id))],indent=2));return
            if args.command=='put':identifier,name,cidr,enabled=args.id,args.name,args.cidr,args.enable
            else:
                existing=db.scalar(select(NetworkPolicy).where(NetworkPolicy.network_id==args.id).with_for_update())
                if existing is None:parser.error('Network policy not found')
                identifier,name,cidr,enabled=existing.network_id,existing.network_name,existing.network_cidr,args.command=='enable'
            row=put_policy(db,network_id=identifier,name=name,cidr=cidr,enabled=enabled,actor=getpass.getuser(),now=local_now(settings))
            print(json.dumps(dict(network_id=row.network_id,network_cidr=row.network_cidr,enabled=row.enabled)))
    except ValueError as exc:parser.error(str(exc))
    finally:engine.dispose()

if __name__=='__main__':main()
