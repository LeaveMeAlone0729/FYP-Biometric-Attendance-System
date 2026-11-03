# B3 real-tablet face scanning diagnosis and retest

## Observed failure (1 November 2026)

Tablet 7732690b (Xiaomi 2410CRP4CG) automatically uploaded camera frames to the dedicated device-approval face endpoint. FastAPI returned HTTP 200 in approximately 200–500 ms. Safe stage logs showed decoded images of 960 x 540 and recoverable FACE_TOO_SMALL / FACE_COUNT_INVALID results. Those requests did not reach template matching. USB reverse was present; the observed failure was not an unreachable backend.

The fixed 180 x 220 preview guide did not scale with a tablet preview. Recoverable detection feedback was placed below the preview while another loading indicator suggested continued processing. Capture/file waits also lacked bounds, and network recovery could silently repeat an unchanged FACE stage. A visible face alone does not meet the existing partner detection, size, position and matching requirements.

## Changes

- Display camera/scanning, detection guidance, mismatch, network failure, timeout, expiry and verified states above the preview.
- Scale the visual oval with the preview in portrait and landscape; preserve CameraPreview rotation/mirroring and upload the original capture for the existing server decoder.
- Serialize captures; allow at most eight consecutive recoverable adjustments, two seconds apart. Pause with instructions after the limit. Genuine server face matching alone advances to liveness.
- Bound capture (8 s), file read (5 s), frame HTTP (15 s) and status recovery (5 s). Stop on expiry even while busy. Ignore late results after ending/restarting.
- Resolve an uncertain frame response once through the bound status endpoint. Resume only if the server advanced; otherwise show the error.
- Correlate device-only HTTP and backend decode/detection/matching/response stages with X-Request-ID. Logs contain codes, timing and dimensions, never images, templates, tokens or bodies.

No matching thresholds, partner algorithms, attendance routes, registration records, or Keystore aliases changed. No schema migration is required. Slot 2 activation remains disabled; even successful B3 checks produce only COMPLETED_UNTRUSTED.

## Windows USB retest

Keep the backend running from the project root:

```powershell
.\backend\venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Use another PowerShell window:

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb -s 7732690b reverse tcp:8000 tcp:8000
Set-Location C:\FYP\FYP-Biometric-Attendance-System\frontend
& C:\Users\yap10\flutter\bin\flutter.bat build apk --debug --dart-define=API_BASE_URL=http://127.0.0.1:8000
& $adb -s 7732690b install -r .\build\app\outputs\flutter-apk\app-debug.apk
```

Do not pass the Pixel_Tablet webcam profile for a physical tablet. Do not uninstall or clear app data. Open the app, log in if needed, open My Device and renew expired candidate preparation using the retained key. Start device facial verification. Keep exactly one well-lit face centered and fill the responsive oval; follow visible guidance. A genuine match displays Face verified and Step 2. A mismatch must stop with feedback. Test portrait and landscape separately. No-face should produce feedback and pause after eight unsuccessful captures; disabling network should stop with an error rather than an endless spinner. Restart only after correcting the issue; creation and frame rate limits still apply.

Safe Flutter diagnostics:

```powershell
& $adb -s 7732690b logcat -d -s flutter:I | Select-String 'B3_HTTP|B3_SCAN'
```

Match B3_HTTP request_id to backend device_biometric request_id. The backend response includes additive feedback_code; the actual server stage and flags remain authoritative. Never paste raw camera data, tokens, or template values into diagnostics.

## Automated verification

126 backend tests completed (one optional test skipped), including isolated MariaDB checks, device enrollment, signature/replay and attendance regressions. 95 Flutter tests passed, including genuine-match-to-liveness, wrong/no-face feedback, network failure, late responses, hung create/capture/upload, expiry while busy, retry bounds, safe diagnostics and tablet layout. Flutter analyze was clean. Physical tablet 7732690b retest confirmed Step 2. Server audit recorded FACE_MATCHED_UNTRUSTED at 2026-11-01 01:31:16 and BIOMETRICS_COMPLETED_UNTRUSTED at 01:31:51 (Asia/Kuala_Lumpur). The session completed with three valid liveness frames. Correlated Flutter logs showed host 127.0.0.1:8000 and the COMPLETED_UNTRUSTED response. Post-test hashes for students, registered_devices and attendance still match the saved B3 baseline, and ACTIVE Slot 2 count remains zero. Portrait and landscape automated layouts passed; the user did not identify which physical orientation produced the successful match.
