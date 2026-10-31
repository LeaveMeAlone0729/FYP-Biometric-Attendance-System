"""B3 results are always untrusted, non-consumable and ineligible for activation."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class DeviceBiometricResult(BaseModel):
    success: Literal[True] = True
    approval_id: str
    pending_registration_id: str
    candidate_device_id: str
    public_key_fingerprint: str
    operation: Literal["enroll_second_device"] = "enroll_second_device"
    slot_number: Literal[2] = 2
    stage: Literal["FACE","LIVENESS","COMPLETED_UNTRUSTED","FAILED","EXPIRED"]
    ready: bool = False
    feedback_code: str
    face_verified: bool
    liveness_verified: bool
    complete: bool
    fingers: int | None
    valid_frames: int
    required_frames: Literal[3] = 3
    expires_at: datetime
    expires_in: int
    result_classification: Literal["UNTRUSTED_TEST_RESULT"] = "UNTRUSTED_TEST_RESULT"
    trusted: Literal[False] = False
    activation_eligible: Literal[False] = False
    consumable: Literal[False] = False
    activation_enabled: Literal[False] = False
    message: str
