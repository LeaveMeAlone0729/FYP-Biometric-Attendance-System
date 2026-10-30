"""Standalone status checks only; attendance operations are not enabled yet."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class VerificationChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["device_status"]


class VerificationRequest(VerificationChallengeRequest):
    challenge_id: str = Field(min_length=20, max_length=64)
    signature: str = Field(min_length=1, max_length=256)


class VerificationFailureRequest(VerificationChallengeRequest):
    challenge_id: str = Field(min_length=20, max_length=64)
    reason_code: Literal["LOCAL_KEY_MISSING", "LOCAL_KEY_MISMATCH", "KEYSTORE_UNAVAILABLE"]


class VerificationChallengeResponse(BaseModel):
    success: Literal[True] = True
    challenge_id: str
    device_id: str
    operation: Literal["device_status"]
    public_key_fingerprint: str
    algorithm: Literal["ECDSA_P256_SHA256"] = "ECDSA_P256_SHA256"
    signature_encoding: Literal["base64-DER"] = "base64-DER"
    signing_payload: str
    expires_at: datetime


class VerificationResponse(BaseModel):
    success: Literal[True] = True
    result: Literal["PASS"] = "PASS"
    verification_id: int
    challenge_id: str
    device_id: str
    operation: Literal["device_status"]
    verified_at: datetime
    challenge_expires_at: datetime
    attendance_authorized: Literal[False] = False


class VerificationFailureResponse(BaseModel):
    success: Literal[True] = True
    result: Literal["FAIL"] = "FAIL"
    code: str
