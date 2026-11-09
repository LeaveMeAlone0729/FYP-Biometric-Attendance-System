# Phase 4B — standalone experimental classroom BLE verification

Branch SH, isolated backend 8002 / MariaDB 3322 only. Phase 4C attendance
integration is **not enabled**. Existing attendance, IP/CIDR, Wi-Fi BSSID,
PIN/session, Keystore, face/liveness and duplicate rules are unchanged.

## Status and assurance

The user confirmed Phase 4A hardware tests: Samsung SM-A346E legacy advertising
works with nRF Connect; Xiaomi saw the test UUID near (-55 dBm median, 23 samples),
far (-101 dBm median, five samples), and not when advertising stopped. These are
**user-reported Phase 4A observations**, not execution of the new signed 4B API.
They do not calibrate a production threshold or establish classroom separation.

A valid Keystore signature identifies which ACTIVE registered device submitted
the report. It does not attest that RSSI or BLE packets are genuine. A static
service UUID can be copied, rebroadcast or relayed; a modified client can fabricate
measurements/timestamps. Equal RSSI values can be legitimate; distinct timestamps
are required, but they are still client reports. No BLE result is campus-IP proof,
institution-verified presence, or attendance authorization.

## Implemented architecture

- New `backend/modules/classroom_ble/` routers, service, policies and separate
  metadata reuse the existing classroom IDs and device authentication/crypto.
- Routes are installed only in `manual_android_test.py`, not the production app
  factory. No public operator mutation API exists.
- Four additive tables: `classroom_ble_policies`, `classroom_ble_challenges`,
  `classroom_ble_events`, `classroom_ble_policy_events`.
- Native BLE diagnostics retains its eight-second limit and Stop action. It now
  records per-service-UUID sample offsets from packets actually received, rather
  than tagging old RSSI values with an identifier cached from an earlier packet.
- Scan owner IDs isolate the general diagnostics card from verification. A
  diagnostics card leaving the viewport cannot cancel a challenge-owned scan.
- Only the explicit **Verify classroom BLE** action scans/signs/uploads. General
  BLE Diagnostics remains local-only. No pairing, automatic enablement or
  background scanning is added. The existing Android permissions remain intact.

## Policy and operator commands (PowerShell 7)

Each policy contains ID, classroom, canonical 128-bit service UUID, optional label,
enabled/retired state, sample minimum, median threshold, maximum sample age,
simulation-only flag, revision and creation/update timestamps.

Defaults are **disabled**, minimum five observations, median threshold **-65 dBm**,
maximum age **15 seconds**. They are experimental defaults, not calibrated campus
values. Allowed ranges: minimum 3–50, threshold -127–0 dBm, age 10–30 seconds.
Policies must be explicitly enabled. Multiple policies are ORed; any approved
beacon meeting its own criteria may PASS. At most eight enabled policies covering
four distinct UUIDs are accepted per classroom. Removal retires/disables without
deleting audit history and cannot be reversed; use a new policy ID if needed.

The live disposable database was migrated but **no policy was seeded/enabled**.

```powershell
cd C:\FYP\FYP-Biometric-Attendance-System
.\fyp-test.ps1 status
.\fyp-test.ps1 ble list

# Add once, initially DISABLED:
.\fyp-test.ps1 ble add --id classroom-a-samsung-test --classroom CLASSROOM_A --uuid 7d9a6c10-326a-4c60-9e01-1ef000000001 --label 'Samsung test beacon - experimental' --minimum-samples 5 --threshold -65 --max-age-seconds 15 --simulation
.\fyp-test.ps1 ble list --classroom CLASSROOM_A
# Explicit operator enable:
.\fyp-test.ps1 ble enable --id classroom-a-samsung-test

# Reversible disable/re-enable:
.\fyp-test.ps1 ble disable --id classroom-a-samsung-test
.\fyp-test.ps1 ble enable --id classroom-a-samsung-test
# Permanent retirement, ONLY when finished:
# .\fyp-test.ps1 ble remove --id classroom-a-samsung-test
.\fyp-test.ps1 ble list --all
```

The existing PS wrapper forwards these implemented `ble` commands to the pinned
offline operator. It cannot take an arbitrary DB URL or fall back to production.
To change threshold/minimum/age, retire the old policy and add a new ID with
reviewed settings, then explicitly enable it. Do not leave a looser old policy
enabled and assume only the new one applies. Shared classroom rows are reused;
no attendance session gets a BLE requirement in this phase.

## Authenticated REST contracts

All three routes require the existing Bearer student session:

1. `GET /api/v1/classroom-ble/classrooms`
   returns `{success:true,simulation_only:true,classrooms:[{classroom_id,name,policies:[...]}]}`.
   Policies expose the reviewed UUID/limits/flags/revision, not nearby-device data.
2. `POST /api/v1/classroom-ble/challenges`

   ```json
   {"classroom_id":"CLASSROOM_A","public_key_fingerprint":"<64 lowercase hex>"}
   ```

   Server verifies current session/student, ownership and ACTIVE public key,
   current enabled policies, and a 20-challenges/student/minute limit. 201 returns
   `success`, `operation:classroom_ble_verification`, `challenge_id`, `classroom_id`,
   `device_id`, `public_key_fingerprint`, `signing_payload` (base64), `expires_at`,
   `approved_policies` and `scan_window_ms:8000`.

   The nonce payload binds student, hashed login session, device/fingerprint,
   classroom, purpose, current enabled-policy hash, server issuance/expiry and a
   random nonce. TTL is 45 seconds or login expiry, whichever is earlier.
3. Flutter obtains a NEW native scan after the nonce, filters approved UUIDs and
   encodes this bounded UTF-8 JSON (illustrative timing, use actual values):

   ```json
   {
     "scan_status":"COMPLETE",
     "bluetooth_enabled":true,
     "scan_permission":"GRANTED",
     "connect_permission":"GRANTED",
     "location_permission":"PRECISE_GRANTED",
     "location_enabled":true,
     "scan_started_at_ms":1794000000000,
     "scan_completed_at_ms":1794000008000,
     "scan_duration_ms":8000,
     "beacons":[{
       "service_uuid":"7d9a6c10-326a-4c60-9e01-1ef000000001",
       "samples":[
         {"offset_us":100000,"rssi_dbm":-55},
         {"offset_us":1100000,"rssi_dbm":-54},
         {"offset_us":2100000,"rssi_dbm":-56},
         {"offset_us":3100000,"rssi_dbm":-55},
         {"offset_us":4100000,"rssi_dbm":-55}
       ]
     }]
   }
   ```

   Offsets use Android's monotonic reception time relative to scan start; cached
   callbacks predating scan start are discarded. No Bluetooth address, name,
   unrelated UUID, manufacturer payload or client-computed median is uploaded.
   At most four UUID groups / 50 total observations / 4500 JSON bytes are allowed.
   The client retains the latest bounded samples, sorts offsets and removes
   duplicate offsets; the backend independently rejects duplicate/unsorted offsets.
4. Sign **decoded server nonce payload + one LF byte + exact observation JSON
   bytes**, base64-encoded for the existing Android Keystore channel. It signs
   SHA256withECDSA P-256 and returns base64 DER. The private key never leaves
   Android. A missing key is not silently recreated. The existing 8192-character
   native signing-input limit is checked before signing.
5. `POST /api/v1/classroom-ble/verifications`

   ```json
   {"challenge_id":"<server challenge>","evidence_payload":"<base64 JSON>","signature":"<base64 DER signature>"}
   ```

   200 returns `success:true`, `result:PASS|FAIL|UNCERTAIN`, `reason_code`, `message`,
   `verification_id`, `challenge_id`, `classroom_id`, `device_id`, `sample_count`,
   backend `median_rssi_dbm`, evaluated threshold/minimum/age, evaluated policy ID,
   matched policy ID (PASS only), `verified_at`, operation,
   `evidence_source:CLIENT_REPORTED_ANDROID_BLE`, `attendance_authorized:false`.
   Proof/schema errors use the existing `{success:false,code,message}` HTTP error
   convention. Client PASS flags, student/device-ID overrides and median fields
   are forbidden. HTTP/transport errors never become a cached authorization.

## Server evaluation and replay handling

The transaction locks student/auth, nonce, ACTIVE device and enabled policy rows.
Wrong-account/session requests cannot consume another owner's challenge. Owned
invalid/expired proofs are consumed and audited. Canonical evidence hashing plus
a student/device/evidence unique constraint rejects the same report re-signed
under another nonce; JSON whitespace, UUID case and beacon-group order do not
create new observations. Policy removal/disable/revision changes after nonce
issuance fail closed. Concurrent confirmations produce at most one successful use.

RSSI values must be integer -127–126 dBm. Offsets must be unique, increasing and
inside the scan. Duration is bounded to ten seconds; a COMPLETE window shorter
than seven seconds is UNCERTAIN. STOPPED/CANCELLED is UNCERTAIN even if some
samples arrived. Future wall timestamps are rejected, scan start must not predate
the exact server issuance time, and every matched sample must meet policy age.
Android/Windows automatic clocks must be aligned; clock skew can legitimately
cause BLE_EVIDENCE_FUTURE/STALE. There is no clock-bypass mode.

Backend computes the median from distinct submitted observations for approved
UUIDs only. No beacon => FAIL. Enough fresh samples and median >= threshold =>
PASS. Below threshold => FAIL. Too few samples => UNCERTAIN. With multiple
policies, any PASS wins; otherwise an UNCERTAIN candidate wins over a definite
FAIL. Unrelated advertisers cannot satisfy a policy. Errors/unavailability do
not prove physical absence.

| Code | Result/meaning |
|---|---|
| BLE_APPROVED | PASS, experimental observation criteria met |
| BLE_BEACON_NOT_FOUND | FAIL, no approved UUID in a complete healthy scan |
| BLE_SIGNAL_WEAK | FAIL, backend median below threshold |
| BLE_INSUFFICIENT_SAMPLES | UNCERTAIN, repeat a full scan |
| NO_ENABLED_BLE_POLICY / BLE_POLICY_CHANGED / BLE_POLICY_INVALID | FAIL, configuration unavailable/changed/invalid |
| BLE_PERMISSION_REQUIRED / BLUETOOTH_OFF / BLE_UNAVAILABLE | UNCERTAIN, no supported classroom decision |
| BLE_SCAN_INCOMPLETE | UNCERTAIN, stopped/short scan |
| BLE_EVIDENCE_STALE / BLE_EVIDENCE_FUTURE | FAIL, timing outside bounds |
| BLE_DUPLICATE_OBSERVATION / BLE_EVIDENCE_REPLAYED | Reject repeated samples/report |
| BLE_EVIDENCE_MALFORMED | Reject invalid/oversized data |
| BLE_CHALLENGE_NOT_FOUND / EXPIRED / REPLAYED | Reject ownership/lifecycle mismatch |
| INVALID_DEVICE_SIGNATURE / DEVICE_NOT_ACTIVE | Reject cryptographic/device prerequisite |

Audit rows retain outcome, binding, policy match, count, median and evidence hash,
not raw scans or authentication tokens. General diagnostics still never uploads.

## Migration, backup and recovery

Verified private backup: `C:\FYP\DB-DeviceManagement\classroom-ble-backup-20261108-0340`.
The existing migration tool now accepts `--component ble`. It verifies the pinned
actual 3322 schema/account/datadir/version, stops only the identity-verified 8002
backend, dumps all 39 pre-existing InnoDB tables with matching private config,
restores into a fresh schema and compares every original row/hash. It runs the
four-table migration twice and CHECK TABLE before applying to the disposable
source, then compares source rows again. No production SQL or schema is touched.

Runtime grants: SELECT policies; SELECT/INSERT/UPDATE challenges; INSERT-only
verification events. Operator policy audits have no runtime grant. Existing
runtime grants remain. No policy is seeded or enabled by migration.

Future explicit repeat (use a NEW private backup folder; already applied here):

```powershell
.\backend\venv\Scripts\python.exe -B backend\migrate_classroom_wifi_test.py --component ble --apply --output C:\FYP\DB-DeviceManagement\ble-backup-NEW-UNIQUE
.\fyp-test.ps1 start --lan
```

If anything fails, the tool leaves the backend stopped. Preserve that backup and
config; restore to another new schema first, compare and review. Do not overwrite
the source or reset its database. The tested recovery path is a verified logical
restore into a separate schema, not destructive rollback over existing records.

## Xiaomi build, update and manual test

No APK was installed automatically. Build uses the existing intended private LAN
URL `http://192.168.0.162:8002`; recheck the operator's READY URL if it has changed.

```powershell
cd C:\FYP\FYP-Biometric-Attendance-System\frontend
flutter build apk --debug --dart-define=API_BASE_URL=http://192.168.0.162:8002
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb devices -l
& $adb -s 7732690b install -r 'C:\FYP\FYP-Biometric-Attendance-System\frontend\build\app\outputs\flutter-apk\app-debug.apk'
if ($LASTEXITCODE -ne 0) { throw 'STOP. Do not uninstall, clear data, or recreate keys.' }
& $adb -s 7732690b shell am start -n com.example.frontend/.MainActivity
```

1. On Samsung use the existing separate nRF Connect legacy advertiser, service
   UUID `7d9a6c10-326a-4c60-9e01-1ef000000001`, small payload/no personal name.
   Keep its original Attend app and Keystore untouched. Advertising success was
   confirmed by the user in Phase 4A; keep the advertiser foreground for this test.
2. Keep Xiaomi/laptop on the reachable home/private LAN. Log in as **FYPTEST001**
   using the existing assigned credentials and ACTIVE tablet key. Enable Bluetooth,
   Nearby Devices, precise location and Location Services through the existing
   diagnostics controls; no silent enable or pairing.
3. Add/enable the policy above. Open Network Verification → **Classroom BLE
   Verification**, Reload BLE policies, select CLASSROOM_A, press Verify.
4. Near beacon: if >=5 approved samples, age passes and backend median >=-65,
   expect PASS. Far: median below -65 should FAIL BLE_SIGNAL_WEAK; fewer than
   five samples => UNCERTAIN. The old 4A counts may differ because only actual
   UUID-tagged packets now count.
5. Stop advertising: a full healthy window should FAIL BLE_BEACON_NOT_FOUND.
   Advertise a different test UUID ending `0002`: it must not satisfy the `0001`
   policy. Other nearby devices remain visible in general diagnostics but are
   filtered out of the upload.
6. Bluetooth OFF/permission denied => UNCERTAIN with the actual reason; backend
   unreachable/timeout => UNCERTAIN, no confirmed policy verdict. Disable policy
   => FAIL NO_ENABLED_BLE_POLICY. Restore only the test settings you intended.

Record actual server code, count, median, threshold, scan duration/age and test
location privately. Repeat multiple windows with transmitter power/interval and
scanner orientation controlled. Phase 4B physical tests are **NOT RUN** until this
new APK/API flow is executed. The earlier 4A radio tests are separate evidence.

BLE diagnostic PASS may coexist with IP/CIDR FAIL: neither diagnostic authorizes
attendance. USB reverse remains invalid campus-IP proof. Do not start a tunnel or
weaken source-IP checks to make a test pass. A connection timeout is never proof
of beacon absence.

## Phase 4C remains separate

Before actual attendance enforcement: evaluate RSSI overlap across real rooms,
agree uncertainty/retention/security semantics, then separately approve mapping
session requirements, immutable attempt snapshots and fresh BLE proof binding to
the existing final writer. Never reuse this standalone PASS or replace current
device/IP/Wi-Fi/PIN/biometric checks. Static beacons/relay and fabricated signed
reports need an explicit threat model; stronger assurance may require authenticated
rotating or challenge-response beacon hardware. No 4C endpoint/adapter is enabled.
