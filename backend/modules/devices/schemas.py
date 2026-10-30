"""Strict device contracts; private keys and client PASS flags are not accepted."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    public_key_spki: str = Field(min_length=40, max_length=1024)
    platform: Literal["android"] = "android"
    device_name: str = Field(min_length=1, max_length=100)
    device_model: str = Field(min_length=1, max_length=150)


class RegistrationConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registration_id: str = Field(min_length=20, max_length=64)
    signature: str = Field(min_length=1, max_length=256)


class RegistrationChallengeResponse(BaseModel):
    success: Literal[True] = True
    registration_id: str
    algorithm: Literal["ECDSA_P256_SHA256"] = "ECDSA_P256_SHA256"
    signature_encoding: Literal["base64-DER"] = "base64-DER"
    signing_payload: str
    expires_at: datetime


class DeviceInfo(BaseModel):
    device_id: str
    device_name: str
    device_model: str
    platform: Literal["android"]
    status: Literal["ACTIVE", "INACTIVE", "REVOKED"]
    public_key_fingerprint: str
    registered_at: datetime


class DeviceResponse(BaseModel):
    success: Literal[True] = True
    device: DeviceInfo | None


class DeviceErrorResponse(BaseModel):
    success: Literal[False] = False
    code: str
    message: str
