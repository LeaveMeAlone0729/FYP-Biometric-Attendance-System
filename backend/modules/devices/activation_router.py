"""Student-authenticated activation; authorization comes only from server trust."""
from fastapi import APIRouter,Depends
from api.dependencies import authenticated,get_context,get_db
from .router import registration_response
from .activation_service import DeviceActivationService
from .activation_schemas import (ActivationReadinessRequest,ActivationChallengeRequest,ActivationConfirmation,
    ActivationReadiness,ActivationChallenge,ActivationAccepted,ActivationStatus)
from .schemas import DeviceErrorResponse

router=APIRouter(prefix='/api/v1/devices/pending-registrations',tags=['Second device activation'],
    responses={code:{'model':DeviceErrorResponse} for code in (403,404,409,410,422,429,503)})
def service(context=Depends(get_context)):return DeviceActivationService(context)

@router.post('/{pending_id}/activation-readiness',response_model=ActivationReadiness)
def readiness(pending_id:str,data:ActivationReadinessRequest,identity=Depends(authenticated),db=Depends(get_db,scope='function'),activation=Depends(service)):
    student,auth=identity
    return registration_response(lambda:activation.readiness(db,student,auth,pending_id))

@router.post('/{pending_id}/activation-challenges',response_model=ActivationChallenge,status_code=201)
def challenge(pending_id:str,data:ActivationChallengeRequest,identity=Depends(authenticated),db=Depends(get_db,scope='function'),activation=Depends(service)):
    student,auth=identity
    return registration_response(lambda:activation.issue(db,student,auth,pending_id,data.approval_id))

@router.post('/{pending_id}/activate',response_model=ActivationAccepted)
def activate(pending_id:str,data:ActivationConfirmation,identity=Depends(authenticated),db=Depends(get_db,scope='function'),activation=Depends(service)):
    student,auth=identity
    return registration_response(lambda:activation.confirm(db,student,auth,pending_id,data.challenge_id,data.approval_id,data.signature))

@router.get('/{pending_id}/activation-status',response_model=ActivationStatus)
def status(pending_id:str,identity=Depends(authenticated),db=Depends(get_db,scope='function'),activation=Depends(service)):
    student,auth=identity
    return registration_response(lambda:activation.status(db,student,auth,pending_id))
