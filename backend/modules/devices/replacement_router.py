"""Student-owned target selection; no client-supplied trust decisions."""
from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import Field
from api.dependencies import authenticated, get_context, get_db
from .router import registration_response
from .pending_schemas import PendingRegistrationRequest, PendingRegistrationResponse
from .replacement_service import DeviceReplacementService

class ReplacementRequest(PendingRegistrationRequest):
    slot_number: Literal[1,2]
    old_device_id: str = Field(min_length=1,max_length=64)

router=APIRouter(prefix="/api/v1/devices",tags=["Device replacement"])
def service(context=Depends(get_context)):return DeviceReplacementService(context)

@router.post("/replacements",status_code=201,response_model=PendingRegistrationResponse)
def begin(data:ReplacementRequest,identity=Depends(authenticated),db=Depends(get_db,scope="function"),replacement=Depends(service)):
    student,auth=identity
    return registration_response(lambda:replacement.begin_replacement(db,student,auth,data))

@router.post("/pending-registrations/{pending_id}/cancel",response_model=PendingRegistrationResponse)
def cancel(pending_id:str,identity=Depends(authenticated),db=Depends(get_db,scope="function"),replacement=Depends(service)):
    student,auth=identity
    return registration_response(lambda:replacement.cancel(db,student,auth,pending_id))
