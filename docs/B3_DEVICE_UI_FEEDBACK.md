# B3 device biometric UI feedback

The device-owned screen uses DeviceBiometricGuide and DeviceLivenessPanel from
frontend/lib/modules/devices/widgets/device_biometric_feedback.dart. These are
presentation-only: no inference, HTTP, approval or attendance logic. Partner
CameraScreen is unchanged. Colors follow the partner palette: white checking,
red #EF5350 adjustment, green #35D596 server-confirmed feedback.

Every fresh capture clears previous green/red to checking white. Backend face
position/count errors and rejected gestures turn the guide red. Only a confirmed
face match or accepted server liveness progress turns it green. Green is feedback
for the latest checked frame, not continuous tracking, institutional trust or
activation authorization. The 220 ms decoration animation only draws a state
change; it cannot create verification success.

The face guide keeps the proven responsive oval dimensions. The liveness guide
outlines the full frame, with palm/face separation instructions and the actual
server-generated finger count. Server counters display live progress while scanning. The third accepted frame
switches to a clean completion page, with no live gesture panel or progress bar. Wrong gestures reset progress to the server
value. Existing one-frame-at-a-time capture, bounded retries, timeouts, expiry,
late-response guards, API bindings and camera orientation handling are retained.
An uncertain upload may recover accepted progress from the authenticated status
endpoint; merely reading an unchanged status does not produce green progress.

## Retest on tablet 7732690b

From PowerShell in the project root, with the existing backend running:

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb -s 7732690b reverse tcp:8000 tcp:8000
Set-Location frontend
& C:\Users\yap10\flutter\bin\flutter.bat build apk --debug --dart-define=API_BASE_URL=http://127.0.0.1:8000
& $adb -s 7732690b install -r .\build\app\outputs\flutter-apk\app-debug.apk
& $adb -s 7732690b shell am start -n com.example.frontend/.MainActivity
```

Do not uninstall/clear data or pass the emulator webcam profile. Open My Device,
renew preparation only if expired, and start device facial verification. Check
white during scanning, red after a no-face/position error, green after genuine
server face matching, then the random gesture instructions. Hold the requested
gesture to see 1/3, 2/3 and then the completion result after the third accepted frame. An incorrect gesture should return red and reset
progress. Check portrait and landscape; the guide should retain the existing
orientation/mirroring. Network/expiry failures should remain actionable and stop
loading. Successful completion remains COMPLETED_UNTRUSTED and Slot 2 inactive.

## Validation

- Flutter analyze: no issues.
- Full Flutter suite: 119 passed, including color transitions, no timer-created
  success, pending-liveness neutral state, rejection resets, progress, gesture
  text, phone/tablet portrait/landscape layouts and prior timeout regressions.
- Backend discovery: 129 tests, 122 passed, seven opt-in live/MariaDB tests skipped.
- No backend or API changes and no schema migration. Protected partner inference,
  Flutter camera, attendance writer, device backend service/API adapter and camera
  preview source hashes match their pre-change values.
- This change does not itself claim a new physical-camera test; install the new
  APK in place and follow the checklist above. No Samsung/key/template changes.

## Random challenge audit and completion fix (1 November 2026)

Both partner BiometricService.verify_face and DeviceBiometricService.face use
secrets.randbelow(5) + 1, once after face matching succeeds. The device service
calls the same partner hand inference and requires the same three consecutive
accepted face/gesture frames. No production random or biometric algorithm changed.

Read-only DEMO001 completed-session evidence (session creation, Malaysia time):

| Created | Finger count |
| --- | --- |
| 2026-11-01 01:30:56 | 3 |
| 2026-11-01 01:36:22 | 1 |
| 2026-11-01 02:41:30 | 4 |
| 2026-11-01 02:50:27 | 3 |

These are distinct persisted sessions. No stuck-three challenge was found.
Repeated values are valid random outcomes. Reopening the same unexpired pending
biometric session deliberately returns its existing stage/count/expiry, including
COMPLETED_UNTRUSTED; it does not reroll or extend expiry. A genuinely new session
starts with fingers=null and receives its random challenge after matching. The
three accepted frames validate ONE fixed gesture, not three gesture challenges.
No forced alternation was added. The available records do not identify which
individual repeated UI observation was a reopen versus a fresh random repeat.

The old completion branch rendered DeviceLivenessPanel after completion. It now
returns DeviceBiometricCompletion, displaying face/liveness/device-key PASS,
registration NOT ACTIVE and trusted biometric approval NOT YET AVAILABLE. Device
key PASS describes the server-validated KEY_PROVEN prerequisite of that exact
bound session; it is not a permanent activation grant. Camera/timers stop through
the existing end path. No gesture instructions, scanning progress or activation
button are rendered. Back to My Device returns through the preparation route;
ordinary Back retains its existing preparation navigation behavior. Failures and
expired sessions retain distinct error states and cannot display this completion.

New deterministic backend tests control random draws to cover 1..5, allow fresh
repeated values, prove no rerolls on retry/status/three frames/completed reopen,
and prove wrong gestures reset consecutive progress without changing the challenge.
New Flutter tests cover resource release/no further captures, completed-session
reopen without camera, distinct failure/expiry, responsive phone/tablet completion
and navigation back through preparation. Tests use isolated fixtures only.

Slot 2 remains inactive and the unavailable trusted provider/hard activation stop
are unchanged. No schema changes, production writes, attendance calls from device
enrollment, Samsung/Keystore/template changes, commits, pushes or merges.

Read-only preservation check: students/templates and registered_devices match the
saved pre-B3 hashes; Samsung remains ACTIVE Slot 1, ACTIVE Slot 2 count is zero.
The original three attendance rows also match their backup hash. There is one
newer normal-attendance row (DEMO001, 2026-11-01 02:55:19), with normal attendance
route activity in the server log; it was retained untouched. No attendance HTTP
requests were made by this task, and device-enrollment fixture tests insert zero
attendance records. The updated APK built successfully; physical retesting of this
completion update remains to be performed using install -r as documented above.
