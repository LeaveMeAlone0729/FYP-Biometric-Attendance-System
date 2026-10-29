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
