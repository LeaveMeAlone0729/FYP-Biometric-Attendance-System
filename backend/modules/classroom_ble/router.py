from fastapi import APIRouter,Depends
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from api.dependencies import authenticated,get_context,get_db
from modules.devices.router import registration_response
from modules.classroom_wifi.models import Classroom
from .policies import listing
from .service import BleVerificationService

router=APIRouter(prefix='/api/v1/classroom-ble',tags=['Experimental standalone BLE'])

class Begin(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    classroom_id:str=Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')
    public_key_fingerprint:str=Field(pattern=r'^[0-9a-f]{64}$')

class Confirm(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    challenge_id:str=Field(min_length=40,max_length=64)
    evidence_payload:str=Field(min_length=1,max_length=6000)
    signature:str=Field(min_length=1,max_length=256)

@router.get('/classrooms')
def classrooms(identity=Depends(authenticated),db=Depends(get_db,scope='function')):
    policies=listing(db)
    return dict(success=True,simulation_only=True,classrooms=[dict(classroom_id=c.classroom_id,name=c.name,
        policies=[p for p in policies if p['classroom_id']==c.classroom_id]) for c in db.scalars(select(Classroom).order_by(Classroom.classroom_id))])

@router.post('/challenges',status_code=201)
def begin(data:Begin,identity=Depends(authenticated),db=Depends(get_db,scope='function'),context=Depends(get_context)):
    return registration_response(lambda:BleVerificationService(context).begin(db,*identity,data))

@router.post('/verifications')
def confirm(data:Confirm,identity=Depends(authenticated),db=Depends(get_db,scope='function'),context=Depends(get_context)):
    return registration_response(lambda:BleVerificationService(context).confirm(db,*identity,data))
