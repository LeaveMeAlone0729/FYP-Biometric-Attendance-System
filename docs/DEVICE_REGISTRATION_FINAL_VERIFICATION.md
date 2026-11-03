# Final device-owned Slot 2 registration verification

The implementation is complete on SH. Existing pending, B3, activation REST,
atomic transactions, automatic Flutter signing and navigation are reused. No new
activation service or preparation stage was introduced. Four obsolete B2 unsigned
activation/approval sketch methods were removed; the finished activation service
is the sole activation implementation. The provider contract is an external
institutional dependency, not an unfinished device-owned function.

## Successful cross-process integration demonstration

Command from project root:

```powershell
.\backend\venv\Scripts\python.exe -B backend\tests\run_slot2_end_to_end.py
```

This explicit test-only entrypoint creates a uniquely named disposable MariaDB
database and a loopback HTTP server on an ephemeral port (never production 8000).
Both engine and settings must identify the isolated DB. It reuses the actual
FastAPI app/routes and production Flutter services. No fixture HTTP endpoints,
production provider file, environment switch in app code or production
configuration option was added. Temporary credentials/key files and the isolated
database are disposed after the run; safe result/log/UI evidence is retained.

Observed real HTTP sequence:

1. Authenticate the isolated student; GET registered devices returns one ACTIVE.
2. PendingDeviceService POSTs Slot 2 preparation; server returns a new pending ID.
3. Existing key channel signs the pending payload; POST proof returns KEY_PROVEN.
4. DeviceBiometricApi creates a B3 session, matches a face fixture and submits
   three distinct liveness frames to the real device endpoints.
5. B3 remains COMPLETED_UNTRUSTED. The separate trusted provider fixture supplies
   independent trusted result/grant records for this exact binding. It never
   promotes or copies B3 IDs, flags or results into approval.
6. Production DeviceActivationService GETs final status, POSTs readiness and
   challenge, signs the bound nonce and POSTs activation. Server returns ACTIVE.
7. The production MyDeviceScreen fetches the committed list over real HTTP,
   displays both ACTIVE devices, identifies the current installation and performs
   a new successful automatic Phase 2 signed verification against Slot 2.
8. SQL assertions confirm two ACTIVE rows, exact candidate fingerprint, one
   consumed approval and one successful activation nonce. The full original
   Slot 1 row is unchanged and attendance count remains zero.

Crypto signatures are real ECDSA P-256/SHA-256 in DER/base64 form. The isolated
Flutter key-channel test adapter calls a local software-fixture signer; no Android
private key is exported or replaced. Biometric inference and institutional trust
are controlled test fixtures, not a claim about real camera accuracy or live
institutional approval. Genuine Android key proof and real face/liveness were
verified separately on the physical tablet below.

Latest successful artifacts:

- .work/slot2-e2e-fad0c407cb87/result.json — requests/statuses and committed SQL row evidence.
- .work/slot2-e2e-fad0c407cb87/flutter-evidence.json — 1 ACTIVE to KEY_PROVEN to ACTIVE to displayed 2.
- .work/slot2-e2e-fad0c407cb87/my-device-two-active.png — actual My Device widget using the application theme/font.

The isolated DB was dropped after assertions. There are no fixture tables in
production and no remaining attendance_slot2_e2e_* databases.

## Real tablet verification

Latest regular APK installed successfully using adb -s 7732690b install -r,
preserving app data. USB reverse maps tcp:8000 to the existing production backend.
The student completed genuine face recognition and three-frame liveness.

Production audit confirms automatic activation readiness FAIL/APPROVAL_UNAVAILABLE
at 2026-11-01 04:40:24 and again at 04:40:58 on a revisit (Malaysia time). The latest
biometric session completed at 04:40:24 with three valid frames. No trusted grant
was inserted to force activation. The retained Xiaomi fingerprint is identical
across 11 pending requests, including the installed-app test.

The physical final screen was visually inspected and saved as
.work/slot2-physical-completion.png. It displays:

- Face recognition: PASS
- Liveness detection: PASS
- Device key verification: PASS
- Registration status: NOT ACTIVE
- Trusted biometric approval: NOT YET AVAILABLE
- Device activation: UNAVAILABLE
- Clear institutional-provider explanation and Back to My Device

There is no live preview, loading spinner or activation button. No face image is
in this completion screenshot. The real tablet's behavior is correct for the
missing external provider; this is a finished error path, not a stuck workflow.

## Real REST failure/concurrency matrix

The existing isolated MariaDB test now uses actual authenticated activation
endpoints for wrong student/session (404), incorrect key signature (403), replay
(409), expired challenge (410), duplicate preparation (same pending ID), concurrent
confirmation (one ACTIVE and one ACTIVATION_REPLAYED), final status/list refresh,
and third-device rejection (DEVICE_LIMIT_REACHED). Other activation tests cover
untrusted/missing/expired/reused grants, revision/result mismatch, rollback and
explicit rejection of relabelled B3 test IDs. No attendance is inserted.

## Final checks

- Backend: 150 tests; 149 passed, one optional live-API test skipped. MariaDB tests enabled.
- Flutter regular suite: 132 passed; the opt-in real HTTP test is skipped in the ordinary run and passed separately through its isolated runner.
- Flutter analyze: clean.
- Cross-process MariaDB/HTTP/Flutter integration: PASS, real rendered 2 / 2 ACTIVE devices.
- Physical unavailable-provider test: PASS with matching visible UI and audit evidence.
- Samsung Slot 1, students/templates and attendance match the pre-test hashes.
- Real ACTIVE Slot 2 count: zero; real Xiaomi remains inactive.
- No partner-owned source, biometric algorithm, trust/recovery implementation,
  existing key/alias, production fixture, commit, push or merge was changed.
- No production schema migration was needed in this final verification pass;
  the already-deployed additive activation tables were reused.

## Exact remaining external dependency

The partner supplies approved biometric enrollment/recovery provenance, current
trusted template revisions, a genuinely fresh attendance-free trusted result and
single-use grant for the exact student/login/pending/key/operation/Slot 2 binding,
and the transactional adapter in TRUSTED_BIOMETRIC_PROVIDER_CONTRACT.md. It must
serialize revision invalidation with activation and must never trust legacy
DEMO001/templates automatically or promote COMPLETED_UNTRUSTED.

When a genuine bound grant is available, the already-finished device module
consumes it through readiness/challenge/sign/confirm and refreshes My Device.
No device-owned REST, signing, insertion, recovery or UI connection remains to be
implemented. Partner trusted capture/result issuance is not implemented here.

## Files changed in this final verification pass

- backend/modules/devices/pending_service.py — remove retired unsigned sketches.
- backend/tests/test_pending_device_enrollment.py — assert those entrypoints are absent.
- backend/tests/test_device_activation.py — real REST/MariaDB failure matrix.
- backend/tests/run_slot2_end_to_end.py — opt-in isolated cross-process runner.
- backend/tests/slot2_fixture_signer.py — local test-only actual P256 signer.
- frontend/lib/modules/devices/services/device_activation_state.dart — clarify untrusted display model ownership.
- frontend/test/slot2_end_to_end_test.dart — actual HTTP/services/My Device integration.
- docs/DEVICE_REGISTRATION_FINAL_VERIFICATION.md — this evidence report.
- docs/SECOND_DEVICE_ACTIVATION_INTEGRATION.md — updated final verification link/status.

Private .work evidence remains ignored and must not be committed with credentials.
