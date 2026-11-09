# Device and network UI notice cleanup

6 November 2026, branch SH. Cosmetic changes only in the device/network Flutter
views. Existing uncommitted implementation work was preserved. No backend, model,
authentication, biometric inference, liveness, attendance or native key behavior
was changed. No app installation/data clearing, database operation, key operation,
Git commit/push/merge/reset or public service launch was performed.

## Views cleaned

| View / file | Cleanup |
|---|---|
| modules/devices/screens/my_device_screen.dart | Replaced repeated blue policy explanations with one short face/liveness instruction and a brief attendance reminder; successful automatic verification now uses a plain green-icon result row |
| modules/devices/screens/device_registration_screen.dart | Registered-key confirmation is plain text; removed the blue technical footer; shortened initial-registration and key-retention guidance |
| modules/devices/screens/pending_device_screen.dart | Replacement target and NOT ACTIVE status are plain text; activation success uses a compact result row; Step 2 gives a direct face/liveness instruction; removed duplicate server-approval explanations and generic session/refresh instructions |
| modules/devices/screens/device_biometric_approval_screen.dart | Removed the long static policy banner above the active scan; kept stage, positioning/gesture feedback, progress, timeout and camera errors |
| modules/devices/widgets/device_biometric_completion.dart | Shortened completion heading and explanation; kept every PASS/NOT CONFIRMED, NOT ACTIVE, approval/activation state, error and safe return action |
| modules/networks/screens/network_verification_screen.dart | Shorter introduction and plain attendance reminder; removed static blue disclaimer/ADB development paragraph; successful PASS no longer repeats its reason code/technical message; actual rejection details and connection diagnostics remain |

The global InfoNotice widget and app theme are unchanged. Only nonwarning device/
network notices were removed or converted to plain guidance/result rows. Existing
warning cards remain. Success always has text as well as colour/icon feedback.
Navigation, action callbacks, automatic verification, server-status checks,
signature handling and API calls are unchanged.

## Essential feedback preserved

- Missing-key and backend errors remain visible; no failure is converted into PASS.
- Slot 2/replacement explicitly require face and liveness verification. Key proof
  alone still shows NOT ACTIVE, with pending expiry and next action.
- Repeated preparation is not suggested: the preparation control remains hidden
  after successful key proof, and the next step is face verification.
- The old replacement device stays ACTIVE until approval, and the unaffected slot
  remains unchanged. Candidate-key retention/app-data guidance remains concise.
- Genuine network FAIL retains the actual backend reason code and rejection text.
  Missing/disabled/invalid policies and loopback restrictions are not suppressed.
- Unreachable/timeout failures retain FAIL and connection guidance, explicitly
  saying no network check completed and attendance is blocked. They are not
  relabelled NETWORK_NOT_AUTHORIZED.
- Network PASS remains a diagnostic, with source IP, matched policy and timestamp;
  the short footer says attendance checks the connection again before saving.
- Camera/liveness instructions, red/green guide feedback, frame count and loading/
  timeout handling are unchanged. Device approval/activation failures are visible.

## Partner-owned/shared screens inspected but not edited

- frontend/lib/screens/auth_screen.dart: the blue demo-environment notice could
  become a quiet caption with the same meaning, subject to partner coordination.
  It was left unchanged rather than hiding that the environment is a demo.
- frontend/lib/screens/student_profile_screen.dart: the biometric privacy card
  remains. A less prominent privacy-details presentation could be agreed with the
  partner; privacy content and consent guidance should remain accessible.
- frontend/lib/modules/biometrics/screens/camera_screen.dart: its notice displays
  live face/liveness instructions and result feedback. Keep it; this is functional
  verification guidance rather than duplicate static explanation.

No partner screen, first-enrollment UI, inference function or attendance screen was
edited as part of this cleanup.

## Validation

From frontend:

```powershell
flutter test
flutter analyze
```

Final result: **183 tests passed, one skipped; Flutter analysis found no issues**.
The full suite includes phone/tablet layouts, automatic verification, replacement,
candidate-key retention, untrusted approval rejection, server network PASS/FAIL,
timeout/unreachable handling and attendance preflight blocking capture.

Updated presentation assertions in device_biometric_test.dart and
pending_device_test.dart for the shorter wording. Added checks in
device_verification_test.dart and network_verification_test.dart that successful
views do not contain nonwarning blue InfoNotice cards, while their verified status
and required guidance remain. Existing error/restriction tests still pass.

One initial run failed only because an expiry test expected the old phrase
"Your local key is retained"; it now verifies "Your key is retained". The final
full run passes. Logs are retained in ignored
`.work/ui-notice-cleanup-20261106/flutter-verified.log`,
`analyze-verified.log` and `results-verified.json`.

No physical phone visual test or APK installation was performed. Existing widget
tests cover small phone and tablet/landscape layouts; check the shortened copy on
the intended demo phone during the next separately controlled manual session.
Previous supervisor workbook results remain historical and were not rewritten.
