# Module owner: Chew Zhexuan
# Module: Facial Recognition and Liveness Detection
"""Public response contracts shared through OpenAPI and the integration guide."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ScanAdjustment(BaseModel):
    success: Literal[True]
    ready: Literal[False]
    retryable: Literal[True]
    message: str


class FacePreview(BaseModel):
    success: Literal[True]
    ready: Literal[True]
    preview_only: Literal[True]
    message: str


class FaceRegistered(BaseModel):
    success: Literal[True]
    ready: Literal[True]
    registered: Literal[True]
    message: str


class FaceVerified(BaseModel):
    success: Literal[True]
    ready: Literal[True]
    face_verified: Literal[True]
    stage: Literal["liveness"]
    fingers: int = Field(ge=1, le=5)
    required_frames: int = Field(ge=1)
    expires_at: datetime
    liveness_step: Literal["hand"]
    anti_spoof_verified: Literal[True]
    head_movement_verified: Literal[True]
    message: str


class HeadMovementProgress(BaseModel):
    success: Literal[True]
    ready: bool
    complete: Literal[False]
    stage: Literal["face"]
    liveness_step: Literal["head"]
    head_action: Literal["look_straight", "turn_left", "turn_right", "look_up", "look_down", "blink"]
    head_step: int = Field(ge=1, le=7)
    head_steps: Literal[7]
    held_frames: int = Field(ge=0, le=1)
    required_hold_frames: Literal[2]
    message: str


class LivenessProgress(BaseModel):
    success: Literal[True]
    complete: Literal[False]
    valid_frames: int = Field(ge=0)
    required_frames: int = Field(ge=1)
    ready: bool = False
    liveness_step: Literal["hand"]
    message: str


class AttendanceAccepted(BaseModel):
    success: Literal[True]
    complete: Literal[True]
    face_verified: Literal[True]
    liveness_verified: Literal[True]
    attendance_id: int
    recorded_at: datetime
    message: str


class ChallengeStarted(BaseModel):
    success: Literal[True]
    challenge_id: str
    expires_at: datetime
    course_name: str
    session_id: int
    venue: str
    stage: Literal["face"]
    expires_in: int


class SuccessResponse(BaseModel):
    success: Literal[True]


class VerificationResult(BaseModel):
    success: Literal[True]
    challenge_id: str
    verification_id: int
    student_id: str
    session_id: int
    status: Literal["pending", "success", "failed", "cancelled", "expired"]
    stage: Literal["face", "liveness", "complete"]
    face_verified: bool
    liveness_verified: bool
    face_liveness_verified: bool
    valid_frames: int
    required_frames: int
    expires_at: datetime
    attendance_id: int | None


class VerificationActivity(BaseModel):
    verification_id: int
    result: str
    stage: str
    attempted_at: datetime
    failure_reason: str | None
