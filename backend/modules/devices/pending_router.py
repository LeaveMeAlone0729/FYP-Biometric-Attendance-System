"""Device-owned B2 routes. No activation route and no attendance imports."""
from fastapi import APIRouter, Depends
from api.dependencies import authenticated, get_context, get_db
from .router import registration_response
from .pending_service import PendingEnrollmentService
from .pending_schemas import PendingRegistrationRequest, CandidateProof, PendingRegistrationResponse, CurrentPendingResponse, DeviceApprovalRequest
from .schemas import DeviceErrorResponse

router = APIRouter(prefix="/api/v1", tags=["Pending second-device enrollment"], responses={
    code: {"model": DeviceErrorResponse} for code in (401,403,404,409,410,422,429,503)})


def service(context=Depends(get_context)):
    return PendingEnrollmentService(context)


@router.post("/devices/pending-registrations", status_code=201, response_model=PendingRegistrationResponse)
def begin_pending(data: PendingRegistrationRequest, identity=Depends(authenticated), db=Depends(get_db, scope="function"), enrollment=Depends(service)):
    student, auth = identity
    return registration_response(lambda: enrollment.begin_pending(db, student, auth, data))


@router.get("/devices/pending-registrations/current", response_model=CurrentPendingResponse)
def current_pending(identity=Depends(authenticated), db=Depends(get_db, scope="function"), enrollment=Depends(service)):
    student, auth = identity
    return registration_response(lambda: enrollment.current_pending(db, student, auth))


@router.get("/devices/pending-registrations/{pending_id}", response_model=PendingRegistrationResponse)
def pending_status(pending_id: str, identity=Depends(authenticated), db=Depends(get_db, scope="function"), enrollment=Depends(service)):
    student, auth = identity
    return registration_response(lambda: enrollment.status(db, student, auth, pending_id))


@router.post("/devices/pending-registrations/{pending_id}/proof", response_model=PendingRegistrationResponse)
def candidate_proof(pending_id: str, data: CandidateProof, identity=Depends(authenticated), db=Depends(get_db, scope="function"), enrollment=Depends(service)):
    student, auth = identity
    return registration_response(lambda: enrollment.proof(db, student, auth, pending_id, data.signature))

