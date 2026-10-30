"""Authenticated registration and automatic verification APIs; no attendance dependencies."""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from api.context import AppContext
from api.dependencies import authenticated, get_context, get_db
from api.schemas import ERROR_RESPONSES, ErrorResponse
from .schemas import (DeviceErrorResponse, DeviceResponse, RegistrationChallengeResponse,
                      RegistrationConfirmation, RegistrationRequest)
from .service import DeviceRegistrationError, DeviceRegistrationService
from .verification_schemas import (VerificationChallengeRequest, VerificationChallengeResponse,
    VerificationRequest, VerificationResponse, VerificationFailureRequest, VerificationFailureResponse)
from .verification_service import DeviceVerificationService

router = APIRouter(prefix="/api/v1/devices", tags=["Device registration"], responses={
    **ERROR_RESPONSES, **{code: {"model": DeviceErrorResponse} for code in (403, 404, 409, 410, 429)},
    422: {"model": DeviceErrorResponse | ErrorResponse}})


def service(context: AppContext = Depends(get_context)):
    return DeviceRegistrationService(context)


def registration_response(operation):
    try:
        return operation()
    except DeviceRegistrationError as exc:
        # Return, do not raise: commit the denied attempt/nonce consumption via get_db.
        return JSONResponse(status_code=exc.status,
                            content={"success": False, "code": exc.code, "message": exc.message})


@router.post("/registration-challenges", status_code=201, response_model=RegistrationChallengeResponse,
             operation_id="beginDeviceRegistration")
def begin_registration(data: RegistrationRequest, identity=Depends(authenticated),
                       db=Depends(get_db, scope="function"), devices=Depends(service)):
    student, auth = identity
    return registration_response(lambda: devices.begin(db, student, auth, data))


@router.post("/registrations", status_code=201, response_model=DeviceResponse,
             operation_id="confirmDeviceRegistration")
def confirm_registration(data: RegistrationConfirmation, identity=Depends(authenticated),
                         db=Depends(get_db, scope="function"), devices=Depends(service)):
    student, auth = identity
    return registration_response(lambda: devices.confirm(db, student, auth, data))


@router.get("/current", response_model=DeviceResponse, operation_id="getRegisteredDevice")
def current_device(identity=Depends(authenticated), db=Depends(get_db, scope="function"),
                   devices=Depends(service)):
    student, _ = identity
    return devices.current(db, student)


# Phase 2 reuses authentication and the audit-preserving response boundary.


def verification_service(context: AppContext = Depends(get_context)):
    return DeviceVerificationService(context)


@router.post("/verification-challenges", status_code=201, response_model=VerificationChallengeResponse,
             tags=["Automatic device verification"], operation_id="beginDeviceVerification")
def begin_verification(data: VerificationChallengeRequest, identity=Depends(authenticated),
        db=Depends(get_db, scope="function"), devices=Depends(verification_service)):
    student, auth = identity
    return registration_response(lambda: devices.begin(db, student, auth, data))


@router.post("/verifications", response_model=VerificationResponse,
             tags=["Automatic device verification"], operation_id="confirmDeviceVerification")
def confirm_verification(data: VerificationRequest, identity=Depends(authenticated),
        db=Depends(get_db, scope="function"), devices=Depends(verification_service)):
    student, auth = identity
    return registration_response(lambda: devices.confirm(db, student, auth, data))


@router.post("/verification-failures", response_model=VerificationFailureResponse,
             tags=["Automatic device verification"], operation_id="reportDeviceVerificationFailure")
def report_verification_failure(data: VerificationFailureRequest, identity=Depends(authenticated),
        db=Depends(get_db, scope="function"), devices=Depends(verification_service)):
    student, auth = identity
    return registration_response(lambda: devices.client_failure(db, student, auth, data))
