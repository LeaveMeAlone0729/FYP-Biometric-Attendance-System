"""Shared demo request and error contracts."""

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class FieldIssue(BaseModel):
    field: str
    message: str


class ErrorResponse(BaseModel):
    success: Literal[False]
    message: str
    fields: list[FieldIssue] | None = None


ERROR_RESPONSES = {
    code: {"model": ErrorResponse, "description": description}
    for code, description in {
        400: "Invalid capture, identity mismatch, or invalid input.",
        401: "Missing, invalid, or expired bearer login.",
        403: "Account or verification ownership is not valid.",
        404: "Verification request was not found.",
        409: "Wrong verification stage, duplicate attendance, or closed class.",
        410: "Verification or attendance window expired.",
        422: "Request fields failed validation.",
        429: "Too many attempts or camera frames.",
        500: "Verification is temporarily unavailable.",
        503: "Database is unavailable.",
    }.items()
}


class Registration(BaseModel):
    student_id: str = Field(min_length=3, max_length=11, pattern=r"^[A-Za-z0-9]+$")
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=150)
    password: str = Field(min_length=8, max_length=128)
    group_id: int = Field(gt=0)

    @field_validator("email")
    @classmethod
    def email_format(cls, value):
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value.strip().lower()

    @field_validator("student_id")
    @classmethod
    def uppercase_id(cls, value):
        return value.upper()

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("Enter your full name.")
        return value.strip()


class Login(BaseModel):
    student_id: str = Field(min_length=1, max_length=11)
    password: str = Field(min_length=1, max_length=128)


class PinEntry(BaseModel):
    pin: str = Field(pattern=r"^\d{6}$")
