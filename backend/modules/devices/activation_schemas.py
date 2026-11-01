"""Strict activation REST contracts. No client trust flags or slot selection."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from .schemas import DeviceInfo

class ActivationReadinessRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')

class ActivationChallengeRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    approval_id: str=Field(min_length=1,max_length=64)

class ActivationConfirmation(ActivationChallengeRequest):
    challenge_id: str=Field(min_length=1,max_length=64)
    signature: str=Field(min_length=1,max_length=256)

class ActivationBindingResponse(BaseModel):
    success: Literal[True]=True
    pending_registration_id: str
    candidate_device_id: str
    public_key_fingerprint: str
    operation: Literal['enroll_second_device','replace_device']
    slot_number: Literal[1,2]

class ActivationReadiness(ActivationBindingResponse):
    status: Literal['ELIGIBLE']
    approval_id: str
    trusted_template_revision_id: str
    biometric_result_id: str
    expires_at: datetime

class ActivationChallenge(ActivationBindingResponse):
    biometric_result_id: str
    challenge_id: str
    approval_id: str
    trusted_template_revision_id: str
    algorithm: Literal['ECDSA_P256_SHA256']
    signature_encoding: Literal['base64-DER']
    signing_payload: str
    expires_at: datetime

class ActivationAccepted(BaseModel):
    success: Literal[True]=True
    device: DeviceInfo
    attendance_authorized: Literal[False]=False

class ActivationStatus(ActivationBindingResponse):
    status: Literal['ACTIVE','NOT_ACTIVE','EXPIRED']
    device: DeviceInfo | None
    active_count: int=Field(ge=0,le=2)
    maximum_active_devices: Literal[1,2]=2
    attendance_authorized: Literal[False]=False
