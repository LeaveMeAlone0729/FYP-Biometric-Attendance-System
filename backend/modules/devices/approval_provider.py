"""Server-only partner contract. No HTTP input can instantiate a trusted grant.

An integrated provider must lock a persistent approval and current trust revision,
revalidate the current encrypted-template binding and session, and consume the
approval in the SAME SQLAlchemy transaction as device activation. It must never
commit internally. The default provider remains unavailable; implement the documented server adapter to integrate genuine institutional trust.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from .service import DeviceRegistrationError


@dataclass(frozen=True)
class ApprovalBinding:
    student_id: str
    auth_token_hash: str
    pending_registration_id: str
    candidate_device_id: str
    public_key_fingerprint: str
    slot_number: int = 2
    operation: str = "enroll_second_device"


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
        raise DeviceRegistrationError(403, "BIOMETRIC_TRUST_REQUIRED", "An institution-approved biometric template is required.")
    if approval.consumed_at is not None:
        raise DeviceRegistrationError(409, "APPROVAL_USED", "This biometric approval has already been used.")
    if approval.expires_at <= now or approval.verified_at < now - timedelta(seconds=60):
        raise DeviceRegistrationError(410, "APPROVAL_EXPIRED", "Biometric approval has expired.")
    if approval.verified_at > now or approval.expires_at > approval.verified_at + timedelta(seconds=60):
        raise DeviceRegistrationError(403, "APPROVAL_INVALID", "Biometric approval freshness is invalid.")
    return approval


class UnavailableTrustedApprovalProvider:
    def _unavailable(self, *args, **kwargs):
        raise DeviceRegistrationError(503, "APPROVAL_UNAVAILABLE", "Institutional biometric trust and fresh trusted approval are not integrated. Device remains inactive.")

    current_template_revision = _unavailable
    validate_template_trust = _unavailable
    invalidate_revision = _unavailable
    find_fresh_approval = _unavailable
    validate_fresh_result = _unavailable

    def validate_and_lock(self, db, approval_id, binding, now):
        if not approval_id:
            raise DeviceRegistrationError(403, "BIOMETRIC_TRUST_REQUIRED", "Trusted biometric approval is required.")
        raise DeviceRegistrationError(503, "APPROVAL_UNAVAILABLE", "Trusted biometric approval is not integrated. Slot 2 activation is disabled.")

    def consume(self, db, approval, now):
        raise DeviceRegistrationError(503, "APPROVAL_UNAVAILABLE", "No trusted approval provider is installed.")


def trusted_approval_provider() -> TrustedApprovalProvider:
    """Partner-owned composition seam. Missing adapter always fails closed.

    No environment/client switch. Partner implements this module entrypoint after
    trust/recovery review; it must use the caller's SQLAlchemy transaction.
    """
    from importlib import import_module
    name='modules.biometrics.trusted_device_provider'
    try: module=import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name==name:return UnavailableTrustedApprovalProvider()
        raise DeviceRegistrationError(503,'APPROVAL_UNAVAILABLE','Trusted biometric provider dependencies are unavailable.') from exc
    factory=getattr(module,'create_device_approval_provider',None)
    if not callable(factory):
        raise DeviceRegistrationError(503,'APPROVAL_UNAVAILABLE','Trusted biometric provider entrypoint is unavailable.')
    provider=factory()
    methods=('current_template_revision','validate_template_trust','invalidate_revision',
        'find_fresh_approval','validate_fresh_result','validate_and_lock','consume')
    if not all(callable(getattr(provider,method,None)) for method in methods):
        raise DeviceRegistrationError(503,'APPROVAL_UNAVAILABLE','Trusted biometric provider contract is incomplete.')
    return provider
