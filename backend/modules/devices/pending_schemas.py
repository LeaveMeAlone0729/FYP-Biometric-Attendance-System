"""Strict preparation contracts. No slot choice, trust result or private key input."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .schemas import RegistrationRequest


class PendingRegistrationRequest(RegistrationRequest):
    pass


class CandidateProof(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signature: str = Field(min_length=1, max_length=256)


class PendingRegistrationResponse(BaseModel):
    success: Literal[True] = True
    pending_registration_id: str
    candidate_device_id: str
    public_key_fingerprint: str
    slot_number: Literal[2] = 2
    operation: Literal["enroll_second_device"] = "enroll_second_device"
    status: Literal["CHALLENGE_ISSUED", "KEY_PROVEN", "FAILED", "EXPIRED", "ACTIVATED"]
    algorithm: Literal["ECDSA_P256_SHA256"] = "ECDSA_P256_SHA256"
    signature_encoding: Literal["base64-DER"] = "base64-DER"
    signing_payload: str | None = None
    challenge_expires_at: datetime
    expires_at: datetime
    key_proven_at: datetime | None = None
    activation_enabled: Literal[False] = False
    biometric_approval_status: Literal["UNAVAILABLE"] = "UNAVAILABLE"
    attendance_authorized: Literal[False] = False


class CurrentPendingResponse(BaseModel):
    success: Literal[True] = True
    pending: PendingRegistrationResponse | None


class DeviceApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pending_registration_id: str = Field(min_length=20, max_length=64)
