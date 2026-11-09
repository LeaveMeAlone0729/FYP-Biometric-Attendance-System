"""Server-only partner contract. No HTTP input can instantiate a trusted grant.

An integrated provider must lock a persistent approval and current trust revision,
revalidate the current encrypted-template binding and session, and consume the
approval in the SAME SQLAlchemy transaction as device activation. It must never
commit internally. The built-in provider issues per-operation approvals only after verified enrollment provenance and fresh bound checks. Faculty recovery is outside this app.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from .service import DeviceRegistrationError
from .management_models import MANAGEMENT_TABLES  # Register additive models before fixture/schema creation.


@dataclass(frozen=True)
class ApprovalBinding:
    student_id: str
    auth_token_hash: str
    pending_registration_id: str
    candidate_device_id: str
    public_key_fingerprint: str
    slot_number: int = 2
    operation: str = "enroll_second_device"
    replaced_device_id: str | None = None
    replaced_device_fingerprint: str | None = None


@dataclass(frozen=True)
class TrustedBiometricApproval:
    approval_id: str
    binding: ApprovalBinding
    trusted_template_revision_id: str
    template_trusted: bool
    result: str
    verified_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None
    biometric_result_id: str | None = None


@dataclass(frozen=True)
class TrustedTemplateRevision:
    revision_id: str
    student_id: str
    template_hash: str
    trusted: bool
    invalidated_at: datetime | None = None


@dataclass(frozen=True)
class TrustedBiometricResult:
    result_id: str
    binding: ApprovalBinding
    trusted_template_revision_id: str
    face_verified: bool
    liveness_verified: bool
    verified_at: datetime
    expires_at: datetime
    classification: str = "TRUSTED_SERVER_RESULT"


class TrustedApprovalProvider(Protocol):
    # All lookups lock authoritative DB rows. No client PASS or B3 test promotion.
    def current_template_revision(self, db, student_id: str, now: datetime) -> TrustedTemplateRevision | None: ...
    def validate_template_trust(self, db, revision: TrustedTemplateRevision, now: datetime) -> None: ...
    def invalidate_revision(self, db, student_id: str, revision_id: str, reason: str, now: datetime) -> None: ...
    def find_fresh_approval(self, db, binding: ApprovalBinding, now: datetime) -> TrustedBiometricApproval | None: ...
    def validate_fresh_result(self, db, approval: TrustedBiometricApproval, binding: ApprovalBinding, revision: TrustedTemplateRevision, now: datetime) -> TrustedBiometricResult | None: ...
    def validate_and_lock(self, db, approval_id: str, binding: ApprovalBinding, now: datetime) -> TrustedBiometricApproval: ...
    def consume(self, db, approval: TrustedBiometricApproval, now: datetime) -> None: ...


def validate_approval(approval, approval_id, binding, now):
    """Defense in depth AFTER a server provider loads/locks authentic stored data."""
    if approval is None:
        raise DeviceRegistrationError(403, "BIOMETRIC_TRUST_REQUIRED", "Trusted biometric approval is required.")
    if not isinstance(approval, TrustedBiometricApproval) or approval.approval_id != approval_id or approval.binding != binding:
        raise DeviceRegistrationError(403, "APPROVAL_MISMATCH", "Approval does not belong to this candidate and login.")
    if not approval.template_trusted or not approval.trusted_template_revision_id or approval.result != "PASS":
        raise DeviceRegistrationError(403, "BIOMETRIC_TRUST_REQUIRED", "An enrollment with verified identity provenance is required.")
    if approval.consumed_at is not None:
        raise DeviceRegistrationError(409, "APPROVAL_USED", "This biometric approval has already been used.")
    if approval.expires_at <= now or approval.verified_at < now - timedelta(seconds=60):
        raise DeviceRegistrationError(410, "APPROVAL_EXPIRED", "Biometric approval has expired.")
    if approval.verified_at > now or approval.expires_at > approval.verified_at + timedelta(seconds=60):
        raise DeviceRegistrationError(403, "APPROVAL_INVALID", "Biometric approval freshness is invalid.")
    return approval


def trusted_approval_provider() -> TrustedApprovalProvider:
    """Built-in self-service approval; enrollment provenance is never fabricated."""
    from .management_approval import LocalDeviceApprovalProvider
    return LocalDeviceApprovalProvider()
