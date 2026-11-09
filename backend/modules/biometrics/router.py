# Module owner: Chew Zhexuan
# Module: Facial Recognition and Liveness Detection
"""Biometric HTTP boundary; retain existing URLs for Flutter compatibility."""

from api.context import AppContext
from api.dependencies import authenticated, get_context, get_db
from api.schemas import ERROR_RESPONSES
from fastapi import APIRouter, Depends, File, Form, UploadFile, Request, HTTPException

from .schemas import (
    AttendanceAccepted,
    FacePreview,
    FaceRegistered,
    FaceVerified,
    HeadMovementProgress,
    LivenessProgress,
    ScanAdjustment,
    SuccessResponse,
    VerificationActivity,
    VerificationResult,
)
from .service import BiometricService
from modules.authorization.service import AttendanceAuthorizationService
from modules.devices.router import registration_response

router = APIRouter(responses=ERROR_RESPONSES)


def get_biometric_service(context: AppContext = Depends(get_context)):
    return BiometricService(context)


async def enrollment_fields(request: Request):
    # Identity/assurance can never be overridden by multipart client fields.
    if set(await request.form()) - {'consent', 'file', 'auto_capture', 'preview_only'}:
        raise HTTPException(422, 'Unexpected face enrollment field.')


@router.post(
    "/register-face",
    tags=["Face registration"],
    operation_id="registerFace",
    response_model=ScanAdjustment | FacePreview | FaceRegistered,
    summary="Register the signed-in student’s face once with consent",
)
def register_face(
    _fields=Depends(enrollment_fields),
    consent: bool = Form(
        ..., description="Explicit consent to store an encrypted face template."
    ),
    file: UploadFile = File(..., description="Live camera image, at most 6 MB."),
    auto_capture: bool = Form(
        False,
        description="Use the guided positioning check; detection issues are retryable.",
    ),
    preview_only: bool = Form(
        False, description="Check positioning without storing a template."
    ),
    identity=Depends(authenticated),
    db=Depends(get_db, scope="function"),
    service: BiometricService = Depends(get_biometric_service),
):
    student, auth = identity
    return service.register_face(
        student, db, file, consent, auto_capture=auto_capture, preview_only=preview_only, auth=auth
    )


@router.post(
    "/verify-face",
    tags=["Facial verification"],
    operation_id="verifyFace",
    response_model=ScanAdjustment | FacePreview | HeadMovementProgress | FaceVerified,
    summary="Match the face, pass anti-spoof checks and complete random server-issued facial actions before the finger challenge",
)
def verify_face(
    challenge_id: str = Form(
        ..., description="Identifier returned by /attendance/start."
    ),
    file: UploadFile = File(..., description="New live camera image, at most 6 MB."),
    auto_capture: bool = Form(
        False,
        description="Enable guided positioning with retryable detection feedback.",
    ),
    preview_only: bool = Form(
        False, description="Check the face without advancing to liveness."
    ),
    identity=Depends(authenticated),
    db=Depends(get_db, scope="function"),
    service: BiometricService = Depends(get_biometric_service),
):
    student, auth = identity
    return service.verify_face(
        student,
        auth,
        db,
        challenge_id,
        file,
        auto_capture=auto_capture,
        preview_only=preview_only,
    )


@router.post(
    "/liveness/frame",
    tags=["Liveness"],
    operation_id="submitLivenessFrame",
    response_model=LivenessProgress | AttendanceAccepted,
    summary="Complete three fresh frames with matching face, passive anti-spoof and correct fingers",
)
def liveness_frame(
    request: Request,
    device_challenge_id: str | None = Form(None, max_length=64),
    device_signature: str | None = Form(None, max_length=256),
    classroom_wifi_proof_id: str | None = Form(None, max_length=64),
    challenge_id: str = Form(...),
    file: UploadFile = File(
        ...,
        description="Fresh camera image with one visible face and one hand for identity, passive anti-spoofing and finger-count checks. At most 6 MB.",
    ),
    identity=Depends(authenticated),
    db=Depends(get_db, scope="function"),
    service: BiometricService = Depends(get_biometric_service),
):
    student, auth = identity
    def operation():
        # Student/auth first, before the biometric challenge lock; algorithms unchanged.
        AttendanceAuthorizationService(service.context).identity(db,student,auth)
        return service.liveness_frame(student, auth, db, challenge_id, file,
            request_scope={**request.scope,'classroom_wifi_proof_id':classroom_wifi_proof_id},device_challenge_id=device_challenge_id,device_signature=device_signature)
    return registration_response(operation)


@router.get(
    "/verification/{challenge_id}",
    tags=["Verification results"],
    operation_id="getVerificationResult",
    response_model=VerificationResult,
    summary="Read the server-confirmed verification state without changing it",
)
def verification_result(
    challenge_id: str,
    identity=Depends(authenticated),
    db=Depends(get_db, scope="function"),
    service: BiometricService = Depends(get_biometric_service),
):
    student, auth = identity
    return service.result(student, auth, db, challenge_id)


@router.post(
    "/attendance/cancel/{challenge_id}",
    tags=["Verification results"],
    operation_id="cancelVerification",
    response_model=SuccessResponse,
)
def cancel(
    challenge_id: str,
    identity=Depends(authenticated),
    db=Depends(get_db, scope="function"),
    service: BiometricService = Depends(get_biometric_service),
):
    student, auth = identity
    return service.cancel(student, auth, db, challenge_id)


@router.get(
    "/verification-attempts",
    tags=["Verification results"],
    operation_id="listVerificationActivity",
    response_model=list[VerificationActivity],
)
def attempts(
    identity=Depends(authenticated),
    db=Depends(get_db, scope="function"),
    service: BiometricService = Depends(get_biometric_service),
):
    student, _ = identity
    return service.attempts(student, db)
