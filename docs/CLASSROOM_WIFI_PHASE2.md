# Phase 2 — Classroom Wi-Fi policy diagnostics (SH)

Phase 3 now adds an **optional attendance-bound** integration in
[CLASSROOM_WIFI_ATTENDANCE_PHASE3.md](CLASSROOM_WIFI_ATTENDANCE_PHASE3.md).
The standalone diagnostic PASS described here still never authorizes attendance.

This optional feature is enabled **only** by `backend/manual_android_test.py`,
on the guarded disposable backend **8002**, MariaDB **127.0.0.1:3322**.
The generic/production app factory does not expose these routes. No production
startup configuration, Android key aliases, CIDR decision or attendance writer
has changed. No new Android permissions or Flutter dependencies are needed.

## Assurance and boundaries

PASS means a fresh **signed client-reported observation** matches a configured
simulation policy. SSID/BSSID can be spoofed, relayed or fabricated by a modified
client; an AP can cover multiple rooms/corridors. Android may cache radio values.
Keystore proves possession of the registered key and integrity of the submitted
bytes, **not** authenticity of the radio observation or classroom presence.
RSSI is diagnostic only, never a threshold. No Wi-Fi verdict authorizes attendance.
Institutional AP inventory, real campus testing and a threat model for any later
attendance integration remain separate work. Never infer campus presence from a
Cloudflare address, forwarding headers, SSID alone or a Wi-Fi PASS.

## Data and operator workflow

Five additive InnoDB tables use separate optional metadata:

| Table | Purpose |
|---|---|
| wifi_classrooms | Stable classroom ID/name, future session-reference target |
| classroom_wifi_policies | Multiple AP rows per classroom, optional exact SSID, enabled/retired state |
| classroom_wifi_challenges | Student/session/device/classroom/operation binding, deadlines and consumption |
| classroom_wifi_events | Issuance/PASS/FAIL audit, evidence hash and matched policy ID |
| classroom_wifi_policy_events | Offline operator changes and policy snapshots |

`ClassSession` is unchanged. A later phase may add a nullable foreign key to
`wifi_classrooms.classroom_id` after a separate migration/integration review.
Retirement disables a policy permanently and retains its row/audit. To reconfigure
a retired AP, add a new policy ID. Disabling is reversible. BSSIDs are normalized
to lowercase; malformed, multicast and Android placeholder addresses are rejected.
SSID is case-sensitive, at most 32 UTF-8 bytes. Omitting it means any SSID on that
BSSID is allowed. Policies are ORed: a BSSID-only policy also permits SSID variants
even if another policy for the same BSSID specifies an SSID.

PowerShell 7 (the home policy below was already added; do not add it twice):

```powershell
cd C:\FYP\FYP-Biometric-Attendance-System
.\fyp-test.ps1 start --lan
.\fyp-test.ps1 status
.\fyp-test.ps1 classroom list

# Initial example, only if classroom-a-home does not already exist:
.\fyp-test.ps1 classroom add --classroom CLASSROOM_A --id classroom-a-home --bssid d8:42:a1:9e:de:2f --ssid Ultraman_yap_5Ghz --simulation

# Add a second approved AP for the SAME classroom, optional SSID omitted:
.\fyp-test.ps1 classroom add --classroom CLASSROOM_A --id classroom-a-hotspot --bssid c6:0b:cc:3b:1b:1e --simulation
.\fyp-test.ps1 classroom list --classroom CLASSROOM_A
.\fyp-test.ps1 classroom disable --id classroom-a-hotspot
.\fyp-test.ps1 classroom enable --id classroom-a-hotspot
.\fyp-test.ps1 classroom retire --id classroom-a-hotspot
.\fyp-test.ps1 classroom list --all
```

These commands reuse the existing guarded offline operator connection and cannot
take an arbitrary database URL/port. No policy mutation HTTP endpoint is exposed.
Duplicate IDs and invalid inputs fail; no update overwrites an existing policy.
CIDR commands remain under `fyp-test.ps1 policy ...` and are independent.

## REST and signing contract

Every route requires the existing Bearer login session.

1. `GET /api/v1/classroom-wifi/classrooms`
   returns `{success:true,simulation_only:true,classrooms:[{classroom_id:"CLASSROOM_A",name:"CLASSROOM_A"}]}`.
2. `POST /api/v1/classroom-wifi/challenges`

   ```json
   {"classroom_id":"CLASSROOM_A","public_key_fingerprint":"<64 lowercase hex characters>"}
   ```

   201 returns `success`, `challenge_id`, `operation:classroom_wifi_verification`,
   `classroom_id`, `device_id`, `public_key_fingerprint`, base64 `signing_payload`,
   and ISO `expires_at`. Payload binds a random nonce, authenticated student,
   hashed auth session, registered ACTIVE device/fingerprint, classroom, operation,
   issuance and expiry. Challenge TTL is 45 seconds or login expiry, whichever is
   earlier; issuance is limited to 20 per student/minute.
3. Only **after** the challenge, Flutter reads Android Wi-Fi again. It never uses
   the local diagnostics card's cached reading. The exact UTF-8 JSON observation is:

   ```json
   {"status":"AVAILABLE","connection_type":"WIFI","permission_status":"PRECISE_GRANTED","wifi_enabled":true,"wifi_connected":true,"location_enabled":true,"ssid":"Ultraman_yap_5Ghz","bssid":"d8:42:a1:9e:de:2f","rssi_dbm":-46,"observed_at_ms":1234567890123}
   ```

   `observed_at_ms` above is illustrative; the app supplies current epoch millis.
   Signature bytes = decoded server `signing_payload` + one LF byte (`0x0a`) +
   **exact** observation UTF-8 bytes. Existing `DeviceKeyStore.sign` takes those
   combined bytes base64-encoded, signs SHA256withECDSA P-256, returns base64 DER.
   No key is generated/replaced by classroom verification.
4. `POST /api/v1/classroom-wifi/verifications`

   ```json
   {"challenge_id":"<server nonce ID>","evidence_payload":"<base64 observation UTF-8 JSON>","signature":"<base64 DER ECDSA signature>"}
   ```

   A verified request returns 200 with `success:true`, `result:PASS|FAIL`,
   `reason_code`, `message`, `verification_id`, `classroom_id`, `device_id`,
   `matched_policy_id` (null for FAIL), `verified_at`, `operation`,
   `evidence_source:CLIENT_REPORTED_ANDROID_WIFI`, `attendance_authorized:false`.
   Proof/binding failures return existing `{success:false,code,message}` HTTP
   errors; Flutter displays FAIL with that code. Extra fields/PASS flags are
   rejected. Neither client-provided IP fields nor forwarding headers are used.

The backend locks student/auth, challenge, device and current policy rows within
one commit-before-response transaction. Wrong-account/session requests cannot
consume the owner's nonce. Valid ownership followed by invalid signature/evidence
ends the nonce. It checks ACTIVE status again at confirmation; both slots work.
Evidence must be at most 15 seconds old, no more than 5 seconds in the future,
and no earlier than nonce issuance minus 2 seconds. Keep Android automatic clock
enabled. Timestamp claims are not hardware attestation. Semantic observation
hash uniqueness per student/device blocks re-signing the same reading under a new
nonce, including JSON whitespace/key-order variations. Row locks serialize
concurrent submissions; a unique constraint supplies a second replay barrier.
Do not store images, tokens, private keys or raw observation blobs in logs.

| Code | Meaning |
|---|---|
| CLASSROOM_WIFI_APPROVED | Reported BSSID and optional SSID match |
| WIFI_BSSID_MISMATCH / WIFI_SSID_MISMATCH | Backend-confirmed policy mismatch |
| WIFI_EVIDENCE_MISSING | Redacted/missing BSSID or required SSID |
| WIFI_EVIDENCE_MALFORMED | Invalid fields, values, JSON or address |
| WIFI_PERMISSION_REQUIRED | Precise permission or Location services unavailable |
| WIFI_UNAVAILABLE | Wi-Fi off, disconnected, unsupported or unavailable |
| WIFI_EVIDENCE_STALE | Observation age/clock outside bounds |
| NO_ENABLED_CLASSROOM_POLICY | All classroom policies absent/disabled/retired |
| WIFI_CHALLENGE_NOT_FOUND / EXPIRED / REPLAYED | Invalid login binding or nonce lifecycle |
| WIFI_EVIDENCE_REPLAYED | Observation already used with another nonce |
| INVALID_DEVICE_SIGNATURE | Proof invalid; no policy verdict accepted |
| DEVICE_NOT_REGISTERED / DEVICE_KEY_NOT_REGISTERED / DEVICE_NOT_ACTIVE | Existing device guard rejection |

Timeout/unreachable is a transport FAIL with **no confirmed policy verdict**. It
must never be labeled a BSSID mismatch. Refresh takes a new reading/challenge.
The card clears old results when backgrounded or the selected classroom changes.

## Migration and recovery

`backend/migrate_classroom_wifi_test.py` pins the operator to the known 3322
environment, stops only its identity-verified backend, checks all source tables
are InnoDB, saves a single-transaction logical dump and matching private config,
restores into a freshly named disposable schema, compares every original row
hash/count, runs/validates the migration twice and checks all restored tables.
Only then does it apply the same additive migration to the disposable source.
It never resets or seeds that source. It grants runtime read access to classrooms/
policies, SELECT/INSERT/UPDATE challenges, INSERT-only audit tables; no policy-write
or DDL grant. Existing runtime grants remain intact. No production migration ran.

The backend remains stopped on migration failure. The verified backup and private
configuration must remain outside Git. Do not blindly restore over the live test
database: restore into a separate schema and compare first. The new tables may be
retained if the optional router is disabled; do not drop them to undo a UI change.

For a future fresh test environment, explicitly run the pinned offline migration:

```powershell
.\backend\venv\Scripts\python.exe -B backend\migrate_classroom_wifi_test.py --apply --output C:\FYP\DB-DeviceManagement\classroom-backup-NEW-UNIQUE-NAME
.\fyp-test.ps1 start --lan
```

## Xiaomi home/hotspot comparison with a reachable backend

The tablet cannot currently reach the laptop LAN while joined to the Samsung
hotspot. **Use USB ADB reverse for this separate classroom diagnostic**; keep the
laptop on home Wi-Fi and do not start a tunnel/change CIDR policies. A home build
using the LAN URL will time out on that hotspot; that is not policy rejection.

Build only (no device installation occurs):

```powershell
cd C:\FYP\FYP-Biometric-Attendance-System\frontend
flutter build apk --debug --dart-define=API_BASE_URL=http://127.0.0.1:8002
```

When you approve the tablet update yourself, use an in-place update. Never run
uninstall/clear-data or attempt a recovery install after an error:

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb -s 7732690b reverse tcp:8002 tcp:8002
& $adb -s 7732690b install -r 'C:\FYP\FYP-Biometric-Attendance-System\frontend\build\app\outputs\flutter-apk\app-debug.apk'
if ($LASTEXITCODE -ne 0) { throw 'Update failed. Stop; do not uninstall or clear data.' }
& $adb -s 7732690b shell am start -n com.example.frontend/.MainActivity
```

1. Keep USB connected/debugging authorized; log into the isolated FYPTEST001
   account. My Device must show this installation's existing ACTIVE registration.
   Do not create another key or replace any device.
2. Open Network Verification. Allow precise location and enable Location services.
   Select CLASSROOM_A in the **Classroom Wi-Fi** section. Local diagnostics remain
   separately labeled. Press **Refresh / Verify classroom** on home Wi-Fi.
   Expected: PASS, CLASSROOM_WIFI_APPROVED, matched classroom-a-home.
3. Leave hotspot policy absent/disabled. Switch tablet to Samsung hotspot, keep
   USB/ADB reverse connected. Confirm Phase 1 reads the current hotspot BSSID,
   then Refresh / Verify classroom. Expected: backend FAIL WIFI_BSSID_MISMATCH.
   If hotspot BSSID has changed, record its actual reading; hotspot identifiers
   can change across restarts. Never relabel a timeout as mismatch.
4. Add/enable classroom-a-hotspot using the actual current BSSID. Refresh again:
   expected PASS for that AP too. Home remains permitted independently.
5. Disable home policy while on home: backend FAIL WIFI_BSSID_MISMATCH if another
   classroom AP policy remains enabled, or NO_ENABLED_CLASSROOM_POLICY if none do.
   Re-enable home afterward. No policy result should authorize attendance.
6. Permission denied/Location off => visible WIFI_PERMISSION_REQUIRED (or an
   honest Android unavailable error). Restore permission; refresh to recover.

**Over USB the existing IP/CIDR card and attendance preflight continue rejecting
loopback. This is expected and must not be relaxed.** Use the LAN URL/home Wi-Fi
build separately for later CIDR/attendance tests. USB transport is only a way to
exercise classroom policy evaluation while the two observed APs differ.

Optional cleanup: `& $adb -s 7732690b reverse --remove tcp:8002`.
No physical Phase 2 PASS is claimed until this manual sequence is executed.
