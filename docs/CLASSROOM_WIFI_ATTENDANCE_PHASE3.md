# Phase 3 — optional classroom Wi-Fi attendance authorization

Scope: branch SH, guarded disposable backend 8002 and MariaDB 3322 only.
The production app factory does not install the classroom attendance adapter.
No production migration/configuration, Android key or existing registration changed.

## Integration and ownership

The existing writer remains `services/attendance.py:record_verified_attendance`,
called by `/liveness/frame` after the partner's third accepted gesture frame.
No second attendance-writing route was created. Face/liveness algorithms,
thresholds, random gesture selection, three-frame requirement and camera UI are
unchanged. The partner-owned `modules/biometrics/router.py` has only one optional
multipart proof-ID field and forwards it through the already-used request scope.
`modules/biometrics/service.py`, inference and templates are untouched in this phase.

The shared PIN-start route snapshots the optional classroom requirement. The
device-owned final authorization service checks that snapshot, fresh signed Wi-Fi
receipt and current enabled policy alongside the existing device signature and
actual ASGI source-IP/CIDR verification. The existing writer calls `fresh()` before
and after inserting inside its savepoint: crossing the Wi-Fi freshness deadline
rolls back the insert. Policy rows and the class session remain locked through
the transaction. Error responses commit rejection audits, not attendance.

The ordinary diagnostic PASS from Network Verification has a different purpose
and no attendance binding, so it cannot authorize attendance.

## Data and migration

Three additive tables join the existing Phase 2 optional metadata:

| Table | Purpose |
|---|---|
| session_classroom_requirements | Session PK/FK, nullable classroom FK, revision, update time |
| attempt_classroom_requirements | Attempt PK/FK, session FK, immutable classroom/revision snapshot |
| attendance_wifi_bindings | Wi-Fi nonce PK/FK, attempt FK, attendance-device nonce FK, preflight/final purpose, signed normalized evidence, one-use timestamp |

Existing `class_sessions` columns and rows are unchanged. Old sessions have no
requirement unless explicitly configured. New unconfigured attempts snapshot a
null requirement and do not collect Wi-Fi or request additional permissions.
Attempts started before this integration may continue only when no classroom is
required; a configured session without an attempt snapshot requires a fresh PIN.

Assign/remove increments the requirement revision and is rejected while any
unconsumed, unexpired attendance attempt for that session exists. Identical
assignments are no-ops. Direct/accidental revision changes invalidate old attempts
at authorization; removing a requirement cannot silently downgrade an old snapshot.
Operator changes are audited in the existing classroom policy event table.

The pinned migration tool backs up all 36 pre-existing tables plus matching private
configuration, restores into a new schema, compares all row hashes/counts, runs
the optional migration twice and checks all tables before applying it to 3322.
Runtime gets SELECT session requirements, SELECT/INSERT attempt snapshots, and
SELECT/INSERT/UPDATE receipt bindings. No runtime DDL or policy-write grant.
No requirement was assigned automatically to an existing session.

Signed Wi-Fi observations remain **client-reported**, spoofable/relayable and
potentially OS-cached. Keystore proves key possession and message integrity, not
physical classroom presence. An AP may cover the corridor. RSSI is not a gate.
Normalized SSID/BSSID evidence is now retained in the disposable receipt table
for final re-evaluation/audit; its authorization expires but rows are not silently
deleted. Do not publish that database or raw observations. No images, bearer
tokens, private keys or email credentials are added to diagnostics.

## REST and freshness protocol

1. `/attendance/start` validates PIN, account/group/window, enrolled face state and
   duplicate protection, then freezes the requirement with the new attempt.
2. Existing `/api/v1/attendance/preflight-challenges` returns the usual bound
   device nonce plus `classroom_wifi_required` and nullable `classroom_id`.
   It still checks actual source IP before the camera opens.
3. When required, Flutter calls:

   ```http
   POST /api/v1/classroom-wifi/attendance-challenges
   Authorization: Bearer <current student session>
   ```

   ```json
   {"attendance_challenge_id":"<PIN attempt>","device_challenge_id":"<preflight device nonce>","preflight":true}
   ```

   There is no client-selectable classroom, student or device ID. The server
   derives them from the frozen attempt and ACTIVE device nonce. The response
   uses the Phase 2 challenge contract with operation
   `attendance_classroom_preflight` or `attendance_classroom_final` and its
   signed payload also binds attendance attempt/session, device nonce and
   requirement revision.
4. After receiving the nonce, Flutter reads Android again, signs the exact server
   payload + LF + exact JSON observation with the existing key, and submits to
   existing `/api/v1/classroom-wifi/verifications`. Phase 2 parsing, signatures,
   policy evaluation, rate limits, canonical evidence replay detection and audits
   are reused. There is no client PASS field.
5. A successful receipt ID is supplied as `classroom_wifi_proof_id` in the
   existing preflight JSON. Preflight consumes only its own receipt; PASS remains
   `attendance_authorized:false`.
6. After face matching, the existing device-owned Flutter adapter obtains the
   separate final attendance device nonce. **Before every liveness submission**,
   it requests a fresh classroom nonce (`preflight:false`), reads Android and
   signs again. It may cache the unconsumed device nonce for its existing lifetime,
   but never caches a Wi-Fi PASS. A failed Wi-Fi check stops that upload.
7. The existing multipart `/liveness/frame` carries the usual device proof plus
   `classroom_wifi_proof_id`. Only genuine server biometric completion can reach
   the final writer. That transaction validates receipt ownership, student/login,
   device/fingerprint, attendance device nonce, attempt, session, classroom and
   operation, rechecks policy/freshness and consumes the final receipt once.

Observation age must remain <=15 seconds, no more than 5 seconds in the future,
and not before its Wi-Fi nonce minus 2 seconds. Wi-Fi nonces expire after 45
seconds or login expiry; the existing attempt/device/window deadlines also apply.
New readings before each frame handle time spent in biometrics. If processing
itself crosses a deadline, reject and restart; never widen it or reuse preflight.
Intermediate liveness frames cannot write attendance; the receipt is consumed by
the final authorization, not by an informational progress response.

Errors preserve Phase 2 `WIFI_BSSID_MISMATCH`, `WIFI_SSID_MISMATCH`,
`WIFI_PERMISSION_REQUIRED`, `WIFI_UNAVAILABLE`, `WIFI_EVIDENCE_MISSING`,
`WIFI_EVIDENCE_MALFORMED`, `WIFI_EVIDENCE_STALE`, `WIFI_EVIDENCE_REPLAYED`,
`WIFI_CHALLENGE_EXPIRED/REPLAYED` and `NO_ENABLED_CLASSROOM_POLICY`.
Integration failures include `CLASSROOM_WIFI_PROOF_REQUIRED`,
`CLASSROOM_WIFI_BINDING_MISMATCH`, `CLASSROOM_REQUIREMENT_CHANGED`,
`CLASSROOM_ATTEMPT_NOT_BOUND` and `CLASSROOM_DEVICE_PROOF_MISMATCH/EXPIRED`.
Timeout/unreachable is never called a Wi-Fi mismatch or successful enforcement.

## PowerShell 7 operator commands

Use a NEW simulation classroom to avoid altering the user's Phase 2 policies.
The existing CLASSROOM_A contains both d8:42:... and an explicitly corrected
a8:42:... home policy. **Do not assume which is the current radio.** Read the
actual tablet diagnostics and enter its current BSSID. Original Phase 2 policies
are retained unchanged by this implementation.

```powershell
cd C:\FYP\FYP-Biometric-Attendance-System
.\fyp-test.ps1 start --lan
.\fyp-test.ps1 status
.\fyp-test.ps1 policy list
.\fyp-test.ps1 classroom list
$homeBssid = Read-Host 'Current HOME BSSID from Xiaomi Wi-Fi diagnostics'
# Add once; duplicate IDs safely reject instead of overwriting:
.\fyp-test.ps1 classroom add --classroom PHASE3_A --id phase3-home --bssid $homeBssid --ssid Ultraman_yap_5Ghz --simulation
.\fyp-test.ps1 classroom add --classroom PHASE3_A --id phase3-other --bssid c6:0b:cc:3b:1b:1e --simulation

# Creates a NEW session, prints its generated PIN once after commit:
.\fyp-test.ps1 session create --class FYPATT01 --minutes 30 --classroom PHASE3_A
# Alternative creation with explicit MYT expiry, same day only:
# .\fyp-test.ps1 session create --class FYPATT01 --expires-at 'YYYY-MM-DDTHH:MM:SS+08:00' --classroom PHASE3_A
.\fyp-test.ps1 session list --class FYPATT01

$sessionId = [int](Read-Host 'New session_id printed by create')
.\fyp-test.ps1 session classroom --id $sessionId
# To assign a classroom to an existing SYNTHETIC session with no active attempts:
.\fyp-test.ps1 session classroom --id $sessionId --assign PHASE3_A
# Explicitly remove only when intended and no active attempt exists:
# .\fyp-test.ps1 session classroom --id $sessionId --remove
```

If the class is absent, overlaps another open session, backend is stopped, or an
attempt blocks a change, the operator reports an error and rolls back. Do not
close historical sessions automatically to make creation succeed. Wait or explicitly
close only the test session you intend. `session list` never exposes PIN hashes.

## Xiaomi build/update and physical tests

Current verified LAN listener: `http://192.168.0.162:8002`. Recheck the address
from `fyp-test.ps1 start --lan` if the laptop moves networks. Use **LAN**, not USB
reverse, for attendance; loopback still fails CIDR even if Wi-Fi matches.

```powershell
cd C:\FYP\FYP-Biometric-Attendance-System\frontend
flutter build apk --debug --dart-define=API_BASE_URL=http://192.168.0.162:8002
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb devices -l
# When you approve the in-place Xiaomi update; no uninstall/fallback:
& $adb -s 7732690b install -r 'C:\FYP\FYP-Biometric-Attendance-System\frontend\build\app\outputs\flutter-apk\app-debug.apk'
if ($LASTEXITCODE -ne 0) { throw 'STOP. Preserve app data and keys; do not uninstall.' }
& $adb -s 7732690b shell am start -n com.example.frontend/.MainActivity
```

No device was installed/cleared by this task. The Xiaomi was not attached at the
later inspection; reconnect before updating. Keep laptop/tablet on the home LAN.
Log into isolated FYPTEST001; My Device must recognize its existing ACTIVE key.
Grant precise location and enable Location services. Do not register a new key.

Fastest sequence uses the NEW session/PIN above, negative checks first so a real
PASS does not turn subsequent checks into duplicate failures:

1. **Same authorized IP, wrong classroom BSSID simulation.** Keep the tablet on
   home Wi-Fi; disable only phase3-home, leaving phase3-other enabled:
   `.\fyp-test.ps1 classroom disable --id phase3-home`.
   Enter the new PIN: expect WIFI_BSSID_MISMATCH before camera; no attendance.
   Restore with `classroom enable --id phase3-home`. This is an honest policy
   simulation of being on another AP, not a claim of a real corridor test.
2. **Disabled classroom policy.** Disable both phase3-home and phase3-other;
   enter PIN again. Expect NO_ENABLED_CLASSROOM_POLICY before camera. Re-enable
   both afterward. These commands do not change the session's classroom mapping.
3. **Correct BSSID, unauthorized actual source-IP membership simulation.** The
   current sole enabled CIDR policy is fyp-simulation (192.168.0.0/24). Keep the
   real Wi-Fi/IP unchanged and temporarily configure that policy to a nonmatching
   documentation range. This tests CIDR rejection independently of the AP match;
   it is not a physical second-network test. If additional enabled CIDRs now exist,
   inspect them first rather than claiming rejection from changing only one:

   ```powershell
   cd C:\FYP\FYP-Biometric-Attendance-System
   $snapshot = Join-Path $env:TEMP ("phase3-cidr-" + [guid]::NewGuid() + '.json')
   .\fyp-test.ps1 policy export --id fyp-simulation --output $snapshot
   try {
       .\fyp-test.ps1 policy set --id fyp-simulation --cidr 198.51.100.0/24 --simulation
       # App diagnostics should show classroom PASS, IP FAIL.
       # Enter the new PIN: expect NETWORK_NOT_AUTHORIZED before camera.
       Read-Host 'Complete the negative test, then press Enter to restore'
   } finally {
       .\fyp-test.ps1 policy restore --id fyp-simulation --input $snapshot
   }
   ```

4. **Authorized home attendance PASS.** Restore the CIDR and phase3-home policy.
   Enter the new PIN; complete real face and three genuine liveness frames.
   Expect attendance accepted and exactly one new history row.
5. **Duplicate FAIL.** Re-enter that SAME PIN before closing the session. Expect
   duplicate rejection, no second row. Then explicitly close the new test session:
   `.\fyp-test.ps1 session close --id $sessionId`.

Do not use the Samsung hotspot as a supposed attendance network FAIL if it cannot
reach the LAN backend: a timeout proves no source-IP/BSSID decision. No public
tunnel or proxy change is provided. Real roaming/campus/different-source-IP tests
remain NOT RUN until a legitimately reachable private backend is available.

All five Phase 3 physical cases are NOT RUN by automation. The user's four
successful Phase 2 Xiaomi diagnostic tests are separate evidence. Automated
attendance tests use synthetic inference and disposable P-256 keys and do not
claim real face/liveness or hardware-key verification.
