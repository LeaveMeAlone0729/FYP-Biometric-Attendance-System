# Facial recognition and liveness module

Module owner: **Chew Zhexuan**.

Current scope: facial recognition and liveness detection only. Do not modify
teammate-owned account, device, network, department or attendance business logic.
Use agreed APIs when those services are needed. In shared screens, changes are
limited to the explicitly marked biometric UI and its imports/callbacks.

The source files below carry an ownership comment. Shared demo code is kept
outside these folders so teammates can integrate their modules separately.

```text
backend/
  app.py                          Development application entry point
  application_factory.py          Application setup and router registration
  api/                            Shared authentication, transactions and demo routes
  services/attendance.py          Shared attendance completion integration point
  modules/biometrics/             Chew Zhexuan's backend module
    router.py                     HTTP endpoints and request parsing
    schemas.py                    Public API response contracts
    service.py                    Enrollment, matching and liveness workflow
    inference.py                  Face recognition and MediaPipe hand inference
    templates.py                  Face-template encryption and decryption
    constants.py                  Capture and liveness limits
  tests/
    test_biometric_inference.py    Inference and geometry checks
    test_biometric_api_contract.py OpenAPI and interface checks
    test_workflow.py               Shared end-to-end demo and authorization checks

frontend/lib/
  modules/biometrics/             Chew Zhexuan's Flutter module
    screens/camera_screen.dart    Consent, camera lifecycle, scanning and feedback
    services/biometric_api.dart   Face/liveness requests through the shared client
  screens/student_profile_screen.dart
                                  Shared profile; biometric status/enrollment/support UI is marked
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

For integration, start with [API_INTEGRATION.md](API_INTEGRATION.md). Import the camera and backend biometric services from their module folders.

## Device registration, verification and replacement

The device module lives in backend/modules/devices/ and
frontend/lib/modules/devices/. DeviceKeyStoreChannel.kt owns the Android
Keystore bridge. The device module owns pending key proof, exact slot binding,
registration and verification audit, and atomic activation/replacement.

The partner inference is reused for device-specific face/liveness sessions.
The device module issues approvals against eligible enrollment provenance and
consumes the fresh grant and candidate-key proof at activation. See the
[provider contract](TRUSTED_BIOMETRIC_PROVIDER_CONTRACT.md) and
[self-service workflow](SELF_SERVICE_DEVICE_MANAGEMENT.md). Faculty recovery
and face replacement remain external.

## Phase 4 network verification FR-06

The independent backend/modules/networks and frontend/lib/modules/networks modules own connection-source CIDR checks, policies, audit and student diagnostics. POST /api/v1/networks/verifications accepts only {} and the existing bearer login. Policies are managed only through the trusted local operator CLI; no range is seeded and localhost never implies campus trust. Uvicorn must run with --no-proxy-headers. The existing attendance writer and all partner biometric algorithms remain unchanged; Phase 5 must perform the fresh final-request check before the attendance insert. See [network contract, migration evidence and testing](NETWORK_VERIFICATION_PHASE4.md).

## Phase 5 mandatory final attendance authorization

POST /liveness/frame still owns runtime attendance completion, through the same shared writer. It now requires an attendance-specific signed device nonce and fresh final-request network verification before insertion. The partner attendance service owns facial matching, passive anti-spoof checks and gesture acceptance. Device and network modules own the fresh proof checks at the final write. The shared attendance UI injects the device-owned automatic signing adapter. Existing standalone device/network PASS results cannot authorize attendance. Production policies remain empty and localhost is denied. See [complete authorization contract, changed files, restored-database evidence and safe later phone tests](ATTENDANCE_AUTHORIZATION_PHASE5.md).


Phase 5 readiness refinement: device-owned authorization service/router now expose signed attendance-attempt preflight before camera navigation. The only additional partner-owned change is CameraScreen's presentation-only `initialFailure` result entry, which skips camera initialization/timers. No partner inference, thresholds, templates, gesture state machine, orientation logic or final attendance writer changes. Preflight PASS is never a final attendance grant; the existing final proof/network guard is preserved.

Confirmed FYP first-enrollment policy: the only additional partner-owned changes
are register_face authorization and atomic provenance recording, plus multipart
identity/assurance field rejection in its router. Detection, encoding, thresholds,
gestures and attendance algorithms are unchanged. See [policy and isolated tests](FYP_ACCOUNT_BOUND_ENROLLMENT.md).
