# Reusable Device Slot 1 / Slot 2 replacement

18 November 2026. Runtime implementation and local capability deployment completed. **Neither live device has been replaced or revoked. No live enrollment provenance has been changed.**

## Normal users

The same existing workflow supports either slot. For pre-provisioned students with valid enabled ACCOUNT_BOUND_FYP first enrollment, or institution-verified provenance, replacement is self-service: new installation login → select ACTIVE target slot → own retained key challenge/proof → NEW genuine face/liveness → short-lived single-use replacement grant → signed activation. No faculty/operator action per replacement. ACCOUNT_BOUND_FYP is not INSTITUTION_VERIFIED. Unknown or legacy enrollment is never silently trusted.

## Local-only legacy test accounts

A separate, explicit one-time operator setup records account-level LOCAL FYP / UNVERIFIED evidence from a fresh actual server scan and candidate key proof. This is an auditable test policy, not institutional identity assurance. It takes an account parameter and works for either target slot/model; it is not a per-phone allowlist.

Default is OFF. Only the supported original backend's explicit local-demo profile can load the existing private operator credential plus the new opt-in. DEMO_MODE alone, JSON request fields and ordinary production startup do not enable it. The private file is outside Git:
`%USERPROFILE%\FYP-Original-Local\local-device-management.json`

```json
{"version":1,"enabled":true}
```

This laptop explicitly opted in under user approval. No account was enrolled/upgraded by deployment. The legacy enrollment-only evidence still cannot authorize replacement until separately approved one-time account setup is completed. Partner Local retains its independent normal ACCOUNT_BOUND_FYP profile; do not copy Full private credentials to it.

## Exact physical test sequence (separate live-data approval required)

1. Approve one-time local account verification and the intended real replacement. For the current test the new phone is BRP_NX1 / AB3S6R4B25010212, target Slot 1. This is a test selection, not a policy hardcode. Old Samsung stays ACTIVE until final normal activation. Xiaomi must remain unchanged.
2. On the NEW device, sign in with assigned credentials; My Device → Replace selected slot → Prepare/prove key. Use the same retained candidate key; never clear app data. Old expired requests/scans cannot be reused.
3. Run a fresh actual face/liveness scan for **account setup**. If current provenance is ineligible, the result should accurately state LOCAL_FYP_ACCOUNT_VERIFICATION_REQUIRED. This scan does not activate the phone or grant replacement.
4. While the setup scan/pending/login are still valid, the authorized local operator reads its exact server reference and runs the command below only after the user approves the account transition. The command verifies original pinned DB/live profile, exact account/key/operation/target/source events, and stores a verified private prior-revision backup before writing a NEW signed account anchor. Old evidence is retained and explicitly retired, not deleted/backdated. Valid standard production/FYP assurance is not replaced.

```powershell
Set-Location C:\FYP\FYP-Biometric-Attendance-System
.\backend\venv\Scripts\python.exe .\backend\local_account_verification.py --student 'AUTHENTICATED_STUDENT_ID' --scan 'EXACT_FRESH_SCAN_ID' --confirm LOCAL-FYP-UNVERIFIED --backup-dir 'C:\FYP\Device-Checkpoints\NEW_UNIQUE_ACCOUNT_BACKUP_FOLDER'
```

The parent checkpoint directory must exist; the final backup folder must not. No passwords/tokens/keys are supplied in command arguments. Original scan/pending/login expiry remains strict. Do not execute against an expired scan; collect a new one. This command has NOT been run on the live account during deployment.

5. Cancel the setup pending request through the existing UI/service (or let it expire), then prepare a NEW replacement request and key proof and complete ANOTHER fresh genuine face/liveness scan. Setup completion cannot be relabeled as a replacement result. The new pre-scan observation binds the current revision, student/login, selected slot, old registration/fingerprint, candidate ID/fingerprint and replace_device purpose.
6. Normal activation readiness issues the usual grant (at most 60 seconds and bounded by all prerequisite expiries). Candidate signs the activation challenge. Backend atomically consumes the grant, revokes only the old selected registration and inserts the new ACTIVE registration. Concurrent/expired/replayed/wrong-bound actions reject; failures roll back revocation and consumption.
7. My Device → Refresh on the replacement phone: confirm ACTIVE + signed-device PASS. Check original DB: old target REVOKED, new target ACTIVE, other slot unchanged, at most two ACTIVE devices, attendance hashes unchanged. On the old actual device, fresh protected verification must reject; normal account login can still work. A synthetic old-key test does not count as physical Samsung rejection.
8. Slot 2 uses exactly the same procedure with a different candidate key and selected target. After account setup there is no new operator exception for each replacement. A revoked historical key cannot simply re-register; never clear app data to manufacture a new installation.

## Evidence and security

Enrollment revision assurance remains UNVERIFIED; new LOCAL FYP registrations retain an internal local marker and accurate replacement audit code, not a name prefix. Disabling the local account profile rejects account-scope demo registrations for protected operations. The anchor is reusable enrollment provenance, NOT a reusable device approval: every operation needs a distinct server-observed fresh scan and single-use grant. Student face/biometric algorithms, PIN/CIDR/Wi-Fi/attendance security, TLS/Cloudflare and Android keys are unchanged.

No new tables/migrations. Existing revisions/observations/authorizations/trust events are reused. Account setup backup is private and contains historical evidence metadata; do not commit/share it. No public trust-writing endpoint or hardcoded approval is introduced.

## Rollback / disabling

Deployment alone changed no live provenance or devices. To disable it, set the private flag enabled=false (or preserve/rename that newly added flag) and restart only the verified original FastAPI backend after approval. Existing legacy Slot 2 behavior remains available under its original legacy local profile. Do not touch TLS, MariaDB, admin, gateway or BLE.

**After a future account transition, disabling this capability will intentionally block that account's local-test registrations.** It will not silently restore an old revision or make demo identity production-trusted. Any provenance restoration requires a separately reviewed, audited maintenance decision using the preserved evidence backup; never direct-force ACTIVE or resurrect consumed grants. Completed replacement is not undoable with the pending-request Cancel action.

## Deployment evidence

Find the exact protected checkpoint from:
`C:\FYP\Device-Checkpoints\slot2-preparation-ui-20261118-002857\reusable-deployment-folder.txt`.
It contains before-deployment hashes/ownership, explicit profile record, deployment result, health checks and runtime logs path. Backend owner after deployment: PID 4444 (recheck before future process operations), LAN 192.168.0.162, pinned 8005. Original DB identity attendance_proposal_xampp:3306, diagnostic OFF. No app install, live setup, activation/revocation, schema/policy change, commit or push occurred.
