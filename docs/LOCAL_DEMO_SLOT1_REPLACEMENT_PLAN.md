# Reusable authorized replacement for BOTH device slots

Revised 18 November 2026. Filename retained for continuity; the preceding one-student/one-phone Slot 1 plan is **superseded**. That version is preserved in the private deployment checkpoint. This is an implementation/acceptance plan, not authorization to change live bindings. No service restart, APK install or live activation/revocation has occurred for this revision.

## Readiness and scope

The standard backend already supports replace_device with slot_number 1 or 2. The missing capability is reusable enrollment assurance for legacy LOCAL FYP DEMO accounts; it is NOT missing slot-selection or atomic replacement code. The generic replacement workflow must never hardcode an account ID, handset model, old device name, or target slot. Student/account identity comes from the authenticated session; target slots are validated as 1 or 2.

**Normal-user suitability:** YES for accounts with valid institution-verified enrollment or explicitly enabled school-provisioned ACCOUNT_BOUND_FYP first enrollment. They self-serve using login → selected target → their NEW device's retained key proof → fresh face/liveness → short-lived single-use approval → signed activation. No operator approval per replacement, manual DB editing or special-case phone exception. ACCOUNT_BOUND_FYP is not INSTITUTION_VERIFIED.

**Legacy/unverified identity:** NOT automatically suitable for a production identity claim. Passing a face comparison only proves similarity to the stored template. Unknown provenance must not silently become institution-trusted. For the local FYP demonstration only, introduce the explicitly approved account-level test anchor below. Normal production must not accept that anchor. Existing enrolled faces and provenance must not be overwritten or silently relabeled.

## Existing reusable core to preserve

- replacement_service.begin_replacement: authenticated ownership, ACTIVE exact target, slot 1/2, distinct canonical candidate key, target ID/fingerprint binding and preparation rate/expiry limits.
- pending_service: candidate's actual signed proof and no device activation during preparation.
- biometric_service: genuine unchanged partner face/liveness inference for each operation; no old-completion reuse as approval.
- management_approval: capture a revision/binding observation before scanning; issue a separate DeviceBiometricAuthorization only when the new scan genuinely completes. Its lifetime is at most 60 seconds and bounded by scan/pending/login expiry.
- activation_service: validate account/login, operation, slot, old registration/key, candidate ID/key, current revision, fresh result, grant expiry and unused state; consume grant and revoke ONLY selected target then insert candidate in one transaction/savepoint. Uniqueness enforces at most one ACTIVE registration per slot. Failure rolls back target revocation/grant consumption. Other slot/history/attendance unchanged.
- Existing Android Keystore keys remain non-exportable; no rotation, clearing or copying for replacement. Candidate must use a genuinely different retained key. Old device can still log in to general APIs; protected ACTIVE-device operations reject its revoked key.

## Implemented runtime changes (deployment approved)

### 1. Explicit local-test profile gate

Add a conservative default-OFF local device-management option to the supported local launcher/profile, with an existing per-environment private operator credential. Runtime Session.info receives this capability only from that explicit supported local profile, not request JSON/headers. Ordinary/production startup must refuse or omit it; DEMO_MODE alone is insufficient. Reuse existing private credential protection and add a domain-separated account-anchor signature; do not put secrets in APK, API responses or logs. Full and Partner Local keep separate profiles/credentials. Partner Local first-time ACCOUNT_BOUND_FYP operation remains usable without this legacy-test feature.

Likely files: original_fyp.py / local_fyp.py and their launcher/profile contract, modules/devices/local_demo.py. Preserve legacy Slot-2-only verification as compatibility; it must NOT be the new generic replacement policy.

### 2. One-time account-level LOCAL FYP test verification

Extend the explicit offline verification operator, accepting an authenticated account ID and exact fresh server scan reference rather than hardcoding a student or device model. It must verify:

- active account and unchanged existing enrolled template;
- actual newly completed face/liveness, three required valid frames, fresh scan deadline and matching candidate/login/operation;
- genuinely accepted candidate key-proof audit before the scan; candidate key is distinct for replacement;
- current server-owned target and slot for replacement preparation;
- operator's local-test authority and an explicit LOCAL FYP / UNVERIFIED attestation, not institutional identity.

Create a NEW, auditable account-bound test revision with a recognizable, domain-separated signed evidence format and UNVERIFIED assurance. Retain original evidence/history. If transitioning a legacy current revision, only an explicit backed-up operator action may retire that revision and add the new one; no silent upgrade, template change or historical backdating. Bind the account-level anchor to student/template/source evidence, not to one handset fingerprint. Preserve all existing legitimate active devices and account data.

This setup scan records demo enrollment provenance ONLY. It does NOT create a replacement grant, set a device ACTIVE, change raw COMPLETED_UNTRUSTED to TRUSTED or reuse that scan for a later replacement. Require a new operation/scan after the anchor is established; cancel/expire previous pending operation through the supported path as necessary. Proper newly provisioned ACCOUNT_BOUND_FYP users do not need this local operator step.

Likely files: verify_enrollment_identity.py, local_demo.py, management_approval.py. Reuse existing revision/observation/grant/audit storage; no schema migration is proposed. Stop for approval if storage cannot support the required invariants safely.

### 3. Reusable local-test eligibility, not per-phone exceptions

In the explicitly gated test profile, verify the signed account-level anchor, unchanged template/current revision, correct authenticated account and candidate operation. Allow enroll_second_device only for Slot 2 and replace_device for Slot 1 OR Slot 2. Preserve full target/key/login/nonce binding. Do not accept arbitrary UNVERIFIED revisions, request-supplied PASS, old key-bound evidence as account-level evidence, or test fixtures on a live DB.

Each replacement still runs management_approval.capture_enrollment and issue_device_authorization with a NEW real scan. Normal single-use grants remain operation/candidate/target bound, so enrollment grants cannot authorize replacement. Existing approval consumption stays transactional; there is no file-only one-use approval state.

New locally authorized registrations must retain a server-internal LOCAL DEMO marker/audit provenance while storing ordinary user-entered names. Device verification/attendance must reject these local-test registrations when that local profile is disabled. Preserve existing legitimate local registrations during the explicit anchor transition; no new key, binding/status change or loss of the unaffected slot.

Likely files: local_demo.py, management_approval.py, pending_service.py, replacement_service.py; only minimal activation audit changes if required. Preserve current atomic activation, expiry, signature and uniqueness mechanisms.

### 4. Clear eligibility errors

When the account has legacy key/operation-limited evidence, return an accurate account-verification-required reason instead of repeatedly instructing a fresh scan that cannot qualify. Eligible accounts missing a fresh operation proof still receive FRESH_BIOMETRIC_PROOF_REQUIRED. Distinguish local test assurance from normal supported account-bound/institution provenance without a label prefix. Existing Flutter PendingDeviceScreen, DeviceBiometricApprovalScreen, DeviceActivationService and MyDeviceScreen should be reused; no new registration flow or major UI is proposed.

## Exact generic end-to-end flow

1. On the genuinely new installation, sign in to the authenticated account; select Replace Slot 1 OR Replace Slot 2 and the ACTIVE target. Do not select a device by client label alone.
2. Fresh paired HTTPS readiness; existing candidate key lookup/explicit first creation; server challenge; candidate signs once; server marks KEY_PROVEN. No automatic replay or public fallback.
3. Backend checks an eligible current enrollment anchor. Normal users continue immediately; unknown legacy accounts stop for appropriate enrollment verification. Local legacy test setup is one-time per account, never per handset or replacement.
4. Start a NEW face/liveness session after eligibility. Observe exact revision/template/operation/target/candidate/login before inference. Genuine server completion creates a distinct short-lived grant, never a client PASS.
5. Candidate signs the normal activation challenge; backend locks/revalidates and atomically consumes grant, revokes selected old device and activates candidate in that same slot.
6. Verify new key PASS, old key rejected, other slot unchanged, two ACTIVE devices maximum, no attendance writes. Repeat another replacement using a different candidate and another fresh proof/scan/grant; no manual DB approval per operation.

## Regression acceptance

New test file: backend/tests/test_reusable_replacement_policy.py. Parameterized for BOTH slots against the real LocalDeviceApprovalProvider and genuine REST-shaped first-enrollment/biometric/grant flow using isolated synthetic image inference and real ECDSA. No patched approval provider, demo student/model exception or live database access.

Covers successful replacement and old/new key verification, unaffected slot and two-device limit, activation replay, no fresh scan, wrong candidate signature, expired grant, wrong login, and rollback of target revocation/grant consumption after insertion failure. Existing account-bound, replacement, management and activation tests additionally cover wrong account/operation/target and untrusted provenance.

New local-test anchor/profile behavior will need additional tests BEFORE deployment: default OFF and normal-server denial, generic accounts and both slots, bad operator evidence, account/template mutation, legacy evidence cannot silently qualify, old completed scan cannot create grant, unknown/disabled assurance, old and new local key handling, independent environment credentials and precise audit labels. Existing normal-profile PASS does not prove an unimplemented local extension.

Physical tests remain pending: new candidate key/face/liveness/activation, old-device real proof rejection and both slot preservation. Do not label SQLite/synthetic inference as physical acceptance or a biometric accuracy measurement.

## Deployment approval and safety

No activation/revocation or attendance change is authorized by this plan revision. Before any live legacy-anchor transition/replacement, take a verified scoped backup; compare protected devices, templates, evidence and attendance. Deploy only after explicit approval and new tests pass. Recheck live backend identity/PID, then restart ONLY supported original FastAPI if approved, preserving HTTPS pairing, diagnostic OFF and existing policies. No MariaDB/admin/gateway/Cloudflare restart or APK install without separate approval. Never reuse the old expired scan/request. No commit/push.

**Current state:** generic standard-account replacement and reusable local-test account verification are implemented and deployed in the explicit local profile. New live account setup and real replacement have NOT been performed; they require the separately approved physical steps.

## Fresh validation for this plan revision

- Added 12 parameterized normal-policy cases in test_reusable_replacement_policy.py (six scenarios × Slots 1 and 2). These use actual school-provisioned first-enrollment REST and the normal operation-approval provider with synthetic biometric inference and real ECDSA; no per-model/account exception or patched approval provider.
- Combined new and existing account-bound, replacement and management regression: **60 PASS, 1 SKIPPED**. Real DB connections were blocked in the test process; live integration opt-ins disabled. Log: C:\FYP\Device-Checkpoints\slot2-preparation-ui-20261118-002857\both-slot-policy-tests.log.
- Read-only live check: Samsung SM-A346E Slot 1 ACTIVE, Xiaomi 2410CRP4CG Slot 2 ACTIVE, attendance count 8. No live state changed. Git whitespace check passed apart from existing line-ending warnings.
- The initial plan review preceded approval; the user subsequently approved implementation and backend-only deployment. That deployment is recorded below and excludes live account-evidence transition or device revocation.

## Approved implementation and deployment — 18 November 2026

The preceding NOT IMPLEMENTED / approval-pending sections describe the reviewed plan and are superseded by this result. The user approved implementation and conditional FastAPI-only deployment, explicitly excluding live account-provenance changes and live activation/revocation.

Implemented:
- modules/devices/local_demo.py: default-OFF private profile, domain-separated signed account-level LOCAL FYP anchor (UNVERIFIED), generic both-slot binding and local-only device enforcement; legacy key scope preserved.
- backend/local_account_verification.py: explicit offline operator verification, fresh genuine scan/key/login/target validation, verified prior-revision backup, audited new UNVERIFIED revision; no operation grant or device activation. No live invocation performed.
- management_approval.py: account anchor verification, precise missing-scope reasons, new pre-scan observation and normal fresh grant only after genuine completion; explicit local audit codes.
- pending_service.py/replacement_service.py: mark eligible local-test candidate origin without hardcoded account, model or slot exception. Normal account-bound candidates remain normal.
- activation_service.py: existing atomic replacement unchanged, accurate LOCAL FYP replacement audit label; no user-name prefix.
- original_fyp.py: opt-in Session capability only inside the explicit original local demo profile with its existing private credential; loopback status bit. Standard/Partner Local profile behavior and conservative defaults preserved.
- tests/test_local_account_replacement.py: 20 new generic local-test checks, including both slots, fresh setup vs fresh operation, disabled profile, tampering, wrong key/login/expiry/target, replay, rollback, historical evidence preservation and MySQL DATETIME precision.

Regression: **180 backend PASS / 2 SKIPPED**, including normal account-bound replacement, legacy management, attendance authorization, production guard, original launcher and Partner Local. Live DB connections were blocked during tests. Current source has no Flutter changes for this feature; focused existing Flutter replacement tests run separately. No schema migration/new table required.

Deployed only to this explicitly approved local-test laptop. Private config file local-device-management.json has version=1/enabled=true under FYP-Original-Local; absent/false remains OFF. New backend listener PID **4444**, HTTP 8000 + pinned HTTPS 8005; current LAN 192.168.0.162. MariaDB 54372, admin 50604 and gateway 56012 were preserved. TLS files unchanged, diagnostic OFF, public attendance 404, localhost/LAN/admin/public config healthy. No APK installation.

Before/after protected hashes MATCH for students, registered devices, attendance, enrollment revisions, school provisioning, biometric authorizations, trust audit and network policies. Samsung Slot 1 ACTIVE and Xiaomi Slot 2 ACTIVE; attendance 8. No live account verification/transition or grant was created. Existing local-device eligibility was checked read-only and still permits both existing devices. This is not a fresh physical signed-key proof.

See REUSABLE_DEVICE_REPLACEMENT.md for exact setup and physical-test steps, separate approval gates and rollback limits. The live legacy account still requires the one-time explicit account setup before replacement; merely enabling the capability does not upgrade it.
