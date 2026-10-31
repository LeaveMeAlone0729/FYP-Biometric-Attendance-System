# Facial recognition and liveness module

Module owner: **Chew Zhexuan**.

The source files below carry an ownership comment. Shared demo code is kept
outside these folders so teammates can integrate their modules separately.

```text
backend/
  app.py                          Application setup and router registration
  api/                            Shared authentication, transactions and demo routes
  services/attendance.py          Shared attendance completion integration point
  modules/biometrics/             Chew Zhexuan's backend module
    router.py                     HTTP endpoints and request parsing
    schemas.py                    Public API response contracts
    service.py                    Enrollment, matching and liveness workflow
    inference.py                  Face recognition and MediaPipe hand inference
    templates.py                  Face-template encryption and decryption
    constants.py                  Capture and liveness limits
  biometrics.py                   Compatibility imports for the old file location
  tests/
    test_biometric_inference.py    Inference and geometry checks
    test_biometric_api_contract.py OpenAPI and interface checks
    test_workflow.py               Shared end-to-end demo and authorization checks

frontend/lib/
  modules/biometrics/             Chew Zhexuan's Flutter module
    screens/camera_screen.dart    Consent, camera lifecycle, scanning and feedback
    services/biometric_api.dart   Face/liveness requests through the shared client
  screens/camera_screen.dart      Compatibility export for existing imports
  screens/student_profile_screen.dart
                                  Shared profile; biometric actions are marked
  services/api_client.dart        Shared login, bearer token and HTTP transport

frontend/test/
  auto_scan_test.dart             Biometric scanning and lifecycle checks
  biometric_api_test.dart         Authenticated multipart request checks
```

`backend/models/hand_landmarker.task` is the downloaded MediaPipe asset. It stays
at its existing path and is not claimed as original module source code. The face
recognition and MediaPipe libraries are external dependencies.

The supporting login, class PIN, timetable and attendance history remain in the
demo. Device registration, network verification and campus checks remain outside
this module.

For integration, start with [API_INTEGRATION.md](API_INTEGRATION.md). Existing
backend imports and Flutter camera imports continue working through small
compatibility files; new code should import from the module folders.

## Device registration (Phase 1)

The teammate device module lives in `backend/modules/devices/` and
`frontend/lib/modules/devices/`, with the Android Keystore bridge in
`DeviceKeyStoreChannel.kt`. See [DEVICE_REGISTRATION.md](DEVICE_REGISTRATION.md).
It registers devices only and does not enforce device/network attendance checks.
The facial recognition and liveness algorithms and existing completion stay unchanged.

## Automatic device verification (Phase 2)

`backend/modules/devices/verification_*.py` owns operation/session/device-bound
possession checks and audit. Flutter uses `device_verification_service.dart`;
My Device triggers checks automatically and displays status only. Phase 1
enrollment remains in `device_registration_screen.dart`. Native Keystore aliases
and biometric/attendance code remain unchanged. See [DEVICE_VERIFICATION.md](DEVICE_VERIFICATION.md).

## Stage A — two-slot foundation

The devices module owns slot constraints, collection listing and exact-key
verification selection. `two_device_migration.py` and `migrate_two_devices.py`
provide the controlled upgrade. No partner biometric/attendance files or native
Keystore aliases changed. Second enrollment awaits Stage B; replacement awaits
Phase 3. See [TWO_DEVICE_STAGE_A.md](TWO_DEVICE_STAGE_A.md).

## Stage B2 device-owned preparation

`backend/modules/devices/pending_*.py`, `approval_provider.py`,
`backend/migrate_pending_devices.py` and Flutter `pending_device_*` own candidate
preparation and the fail-closed partner interface. No biometric inference/lifecycle
or attendance files are changed. Partner B1 trust/recovery and an attendance-free
approval provider remain required. See [B2](SECOND_DEVICE_STAGE_B2.md).

## Stage B3 — device biometric tests

Device-owned `biometric_*.py` under modules/devices and the Flutter device biometric
screen/adapter orchestrate attendance-free untrusted tests. They reuse unchanged
partner inference and camera-plugin patterns. No partner algorithm, lifecycle,
attendance or native key source changed. See [B3](SECOND_DEVICE_STAGE_B3.md).

## Stage B4 — disabled final activation preparation

Device-owned activation_models.py, activation_service.py and activation_migration.py
prepare fresh signed activation and per-challenge audit. The old unsigned pending
activation sketch now rejects. migrate_device_activation.py validates only a restored
copy; no production tables/routes are installed. Flutter device_activation_state.dart
keeps automatic activation unavailable. Partner trust/recovery remains a dependency.
See [B4](SECOND_DEVICE_STAGE_B4.md). No partner inference/lifecycle or attendance
source is changed.

## Completed device-owned activation integration

The device module now owns activation_router.py, activation_schemas.py, the B4
transaction core, readiness/status and automatic Flutter device_activation_service.dart.
The migration is deployed; all actual eligibility still requires the partner's
genuine trusted revision/result/grant adapter. No partner source was modified.
See [integration](SECOND_DEVICE_ACTIVATION_INTEGRATION.md) and
[exact provider contract](TRUSTED_BIOMETRIC_PROVIDER_CONTRACT.md).
