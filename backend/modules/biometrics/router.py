# Module owner: Chew Zhexuan
# Module: Facial Recognition and Liveness Detection
"""Biometric HTTP boundary; retain existing URLs for Flutter compatibility."""

from api.context import AppContext
from api.dependencies import authenticated, get_context, get_db
from api.schemas import ERROR_RESPONSES
from fastapi import APIRouter, Depends, File, Form, UploadFile

from .schemas import (
    AttendanceAccepted,
    BiometricRemoved,
    FacePreview,
    FaceRegistered,
    FaceVerified,
    LivenessProgress,
    ScanAdjustment,
    SuccessResponse,
    VerificationActivity,
    VerificationResult,
)
from .service import BiometricService

router = APIRouter(responses=ERROR_RESPONSES)


def get_biometric_service(context: AppContext = Depends(get_context)):
    return BiometricService(context)


@router.post(
    "/register-face",
    tags=["Face registration"],
    operation_id="registerFace",
    response_model=ScanAdjustment | FacePreview | FaceRegistered,
    summary="Register the signed-in student’s face with consent",
)
def register_face(
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
    student, _ = identity
    return service.register_face(
        student, db, file, consent, auto_capture=auto_capture, preview_only=preview_only
    )


@router.delete(
    "/biometrics",
    tags=["Face registration"],
    operation_id="removeFaceRegistration",
    response_model=BiometricRemoved,
    summary="Remove the face template and cancel pending challenges",
)
def remove_biometrics(
    identity=Depends(authenticated),
    db=Depends(get_db, scope="function"),
    service: BiometricService = Depends(get_biometric_service),
):
    student, _ = identity
    return service.remove_biometrics(student, db)


@router.post(
    "/verify-face",
    tags=["Facial verification"],
    operation_id="verifyFace",
    response_model=ScanAdjustment | FacePreview | FaceVerified,
    summary="Match the registered face and issue a random finger challenge",
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
    summary="Check one fresh face/hand frame; complete after three consecutive matches",
)
def liveness_frame(
    challenge_id: str = Form(...),
    file: UploadFile = File(
        ...,
        description="Fresh camera image with one visible face and one hand, at most 6 MB.",
    ),
    identity=Depends(authenticated),
    db=Depends(get_db, scope="function"),
    service: BiometricService = Depends(get_biometric_service),
):
    student, auth = identity
    return service.liveness_frame(student, auth, db, challenge_id, file)


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
